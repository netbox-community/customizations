#Requires -Version 5
<#
.SYNOPSIS
    Synchronize Netbox Virtual Machines from VMware vCenter.
.DESCRIPTION
    The Sync-Netbox cmdlet uses the Django Swagger REST API included in Netbox and VMware PowerCLI to synchronize data
    from vCenter to Netbox.
    Function skeleton adapted from https://gist.github.com/9to5IT/9620683
.PARAMETER Token
    Netbox REST API token
.NOTES
    Version:         1.2
    Author:          Joe Wegner <joe at jwegner dot io>
    Original source: https://github.com/jwegner89/netbox-utilities
    Creation Date:   2018-02-08
    Purpose/Change:  Initial script development
    License:         GPLv3
    Note that this script relies heavily on the PersistentID field in vCenter, as that will uniquely identify the VM
    You will need to create a vcenter_persistent_id custom field on your VM object in Netbox for this to work properly
    removed PowerCLI requires header due to loading error
    Updated to support Netbox v2.9
    #Requires -Version 5 -Modules VMware.PowerCLI
#>

#---------------------------------------------------------[Initialisations]--------------------------------------------------------

#Set Error Action to Silently Continue
#$ErrorActionPreference = "SilentlyContinue"
# allow verbose messages to be recorded in transcript
$VerbosePreference = "Continue"

#----------------------------------------------------------[Declarations]----------------------------------------------------------

# store common paths in variables for URI creation
# update for your Netbox instance
$URIBase = "https://netbox.example.com/api"
$ClustersPath = "/virtualization/clusters"
$VirtualMachinesPath = "/virtualization/virtual-machines"
$PlatformsPath = "/dcim/platforms"
$InterfacesPath = "/virtualization/interfaces"
$IPAddressesPath = "/ipam/ip-addresses"

#-----------------------------------------------------------[Functions]------------------------------------------------------------

function Sync-Netbox {
    param (
        [parameter(Mandatory=$true)]
        [ValidateNotNullOrEmpty()]
        [String]
        $Token
    )
    
    begin {
        # setup headers for Netbox API calls
        $TokenHeader = "Token " + $Token
        $Headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
        $Headers.Add("Accept", "application/json")
        $Headers.Add("Authorization", $TokenHeader)
        
        # first, we will clear out any VMs that are in Netbox but no longer in vCenter
        
        # get all VMs in vCenter and collect their persistent IDs
        $VMs = Get-VM
        $VMCount = "Retrieved $VMs.count from vCenter"
        Write-Verbose $VMCount
        $vCenterPersistentIDs = @()
        foreach ($VM in $VMs) {
            $vCenterPersistentIDs += $VM.PersistentID
        }
        
        # retrieve all VMs from Netbox
        $URI = $URIBase + $VirtualMachinesPath + "/?limit=0"
        $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
        #ConvertTo-JSON $Response | Write-Verbose
        
        # check each Netbox VM against list from vCenter and delete if not present
        foreach ($VM in $Response.Results) {
            $PersistentID = $VM.custom_fields.vcenter_persistent_id
            if ($vCenterPersistentIDs -notcontains $PersistentID) {
                # Delete old VM from Netbox inventory
                $NetboxID = $VM.ID
                $URI = $URIBase + $VirtualMachinesPath + "/" + $NetboxID + "/"
                $Response = Invoke-RESTMethod -Method DELETE -Headers $Headers -ContentType "application/json" -URI $URI
                #ConvertTo-JSON $Response | Write-Verbose
                $Message = "Deleting " + $VM.Name
                Write-Verbose $Message
            }
        }

        # Create mapping of vCenter OSFullName to Netbox platform IDs
        $NetboxPlatforms = @{}
        $URI = $URIBase + $PlatformsPath + "/?limit=0"
        $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
        ConvertTo-JSON $Response | Write-Verbose
        
        foreach ($Platform in $Response.Results) {
            $NetboxPlatforms[$Platform.Name] = $Platform.ID
        }
        
        # Create mapping of vCenter Cluster Names to Netbox cluster IDs
        $NetboxClusters = @{}
        $URI = $URIBase + $ClustersPath + "/?limit=0"
        $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
        ConvertTo-JSON $Response | Write-Verbose
        
        foreach ($Cluster in $Response.Results) {
            $NetboxClusters[$Cluster.Name] = $Cluster.ID
        }
        
        # retrieve all clusters from vCenter
        $Clusters = Get-Cluster
        
        # iterate through the clusters
        foreach ($Cluster in $Clusters) {
            # Retrive Netbox ID for cluster
            $ClusterID = $NetboxClusters[$Cluster.Name]
        
            # Retrieve all VMs in cluster
            $VMs = Get-VM -Location $Cluster
        
            # Iterate through each VM object
            foreach ($VM in $VMs) {
                # Query Netbox for VM using persistent ID from vCenter
                $URI = $URIBase + $VirtualMachinesPath + "/?q=&cf_vcenter_persistent_id=" + $VM.PersistentID
                $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
                ConvertTo-JSON $Response | Write-Verbose
        
                # A successful request will always have a results dictionary, though it may be empty
                $NetboxInfo = $Response.Results
        
                # Retrieve Netbox ID for VM if available
                $NetboxID = $NetboxInfo.ID
        
                # Create object to hold this VM's attributes for export
                $vCenterInfo = @{}
        
                if ($Response.Count -eq 0) {
                    # A machine with this PersistentID does not exist yet, or was created manually
                    $vCenterInfo["custom_fields"] = @{
                        "vcenter_persistent_id" = $VM.PersistentID
                    }
                } elseif ($Response.Count -gt 1) {
                    # duplicate entries exit / something went wrong
                    Write-Warning -Message [String]::Format("{0} has {1} entries in Netbox, skipping...", $VM.Name, $Response.Count)
                    continue
                }
                # don't need to consider case where we have count -eq 1 since we already have the info set
                # and count *shouldn't* be negative...
        
                # calculate values for comparison
                $vCPUs = $VM.NumCPU
                $Disk = [Math]::Round($VM.ProvisionedSpaceGB).ToString()
        
                # Match up VMHost with proper Netbox Cluster
                $VMHost = Get-VMHost -VM $VM | Select-Object -Property Name
		# Our VM hosts have prefixes that match the cluster name, so adjust as needed
                if ($VMHost -match "CLUSTER1") {
                    $ClusterID = $NetboxClusters["CLUSTER1"]
                } elseif ($VMHost -match "CLUSTER2") {
                    $ClusterID = $NetboxClusters["CLUSTER2"]
                }
                if ($NetboxInfo.Cluster) {
                    if ($NetboxInfo.Cluster.ID -ne $ClusterID) { $vCenterInfo["cluster"] = $ClusterID }
                } else {
                    $vCenterInfo["cluster"] = $ClusterID
                }
        
                if ($NetboxInfo.vCPUs -ne $vCPUs) { $vCenterInfo["vcpus"] = $vCPUs }
                if ($NetboxInfo.Memory -ne $VM.MemoryMB) { $vCenterInfo["memory"] = $VM.MemoryMB }
                if ($NetboxInfo.Disk -ne $Disk) { $vCenterInfo["disk"] = $Disk }
        
                if ($VM.PowerState -eq "PoweredOn") {
                    # Netbox status ID 1 = Active
                    if ($NetboxInfo.Status) {
                        if ($NetboxInfo.Status.Label -ne "Active") { $vCenterInfo["status"] = 1 }
                    } else {
                        $vCenterInfo["status"] = 1
                    }
                } else {
                    # VM is not powered on
                    # Netbox status ID 0 = Offline
                    if ($NetboxInfo.Status) {
                        if ($NetboxInfo.Status.Label -eq "Active") { $vCenterInfo["status"] = 0 }
                    } else {
                        $vCenterInfo["status"] = 0
                    }
                }
        
                # Retrieve guest information
                $Guest = Get-VMGuest -VM $VM
        
                # canonicalize to lower case hostname
                if ($Guest.Hostname) {
                    $Hostname = $Guest.Hostname.ToLower()
                    # Convert Guest OS name to Netbox ID
                    if ($NetboxInfo.Name -ne $Hostname) { $vCenterInfo["name"] = $Hostname }
                } else {
                    # Use VM inventory name as a placeholder - uniquely identified by PersistentID
                    $Name = $VM.Name.ToLower()
                    if ($NetboxInfo.Name -ne $Name) { $vCenterInfo["name"] = $Name }
                }
        
                # Lookup Netbox ID for platform
                if ($Guest.OSFullName) {
                    $Platform = $Guest.OSFullName
                    # check that this platform exists in Netbox
                    if ($NetboxPlatforms.ContainsKey($Platform)) {
                        $PlatformID = $NetboxPlatforms[$Platform]
                        if ($NetboxInfo.Platform) {
                            if ($NetboxInfo.Platform.ID -ne $PlatformID) { $vCenterInfo["platform"] = $PlatformID }
                        } else {
                            $vCenterInfo["platform"] = $PlatformID
                        }
                    } else {
                        # platform not present in Netbox, need to create it

                        # strip out bad character for friendly URL name
                        $Slug = $Platform.ToLower()
                        $Slug = $Slug -Replace "\s","-"
                        $Slug = $Slug -Replace "\.",""
                        $Slug = $Slug -Replace "\(",""
                        $Slug = $Slug -Replace "\)",""
                        $Slug = $Slug -Replace "/",""
                        Write-Verbose "Creating new platform:"
                        $PlatformInfo = @{
                            "name" = $Platform
                            "slug" = $Slug
                        }
                        $PlatformJSON = ConvertTo-JSON $PlatformInfo
                        Write-Verbose $PlatformJSON
                        $URI = $URIBase + $PlatformsPath + "/"
                        $Response = Invoke-RESTMethod -Method POST -Headers $Headers -ContentType "application/json" -Body $PlatformJSON -URI $URI
                        ConvertTo-JSON $Response | Write-Verbose
                        # add new id into platforms hashtable
                        $NetboxPlatforms[$Response.Name] = $Response.ID
                    }
                }
        
                # Store results with defaults from previous request
                $NetboxVM = $NetboxInfo
                # Check if we have any changes to submit
                if ($vCenterInfo.Count -gt 0) {
                    # Create JSON of data for POST/PATCH
                    $vCenterJSON = ConvertTo-JSON $vCenterInfo
                    if ($NetboxID) {
                        # VM already exists in Netbox, so update with any new info
                        Write-Verbose "Updating Netbox VM:"
                        Write-Verbose $vCenterJSON
                        $URI = $URIBase + $VirtualMachinesPath + "/$NetboxID/"
                        $Response = Invoke-RESTMethod -Method PATCH -Headers $Headers -ContentType "application/json" -Body $vCenterJSON -URI $URI
                        ConvertTo-JSON $Response | Write-Verbose
                        $NetboxVM = $Response
                    } else {
                        Write-Verbose "Creating new VM in Netbox:"
                        Write-Verbose $vCenterJSON
                        # VM does not exist in Netbox, so create new VM entry
                        $URI = $URIBase + $VirtualMachinesPath + "/"
                        $Response = Invoke-RESTMethod -Method POST -Headers $Headers -ContentType "application/json" -Body $vCenterJSON -URI $URI
                        ConvertTo-JSON $Response | Write-Verbose
                        $NetboxVM = $Response
                    }
                } else {
                    $VMName = $NetboxInfo.Name
                    Write-Verbose "VM $VMName already exists in Netbox and no changes needed"
                }
                $NetboxID = $NetboxVM.ID
        
                # Create list to store collected NIC objects
                $vCenterNICs = @()
                if ($Guest.NICs) {
                    foreach ($NICInfo in $Guest.NICs) {
                        foreach ($NIC in $NICInfo) {
                            # Check that the device name exists
                            if ($NIC.Device.Name) {
                                # Process each IP in array
                                $IPs = @()
                                foreach ($IP in $NIC.IPAddress) {
                                    $vCenterIP = [IPAddress]$IP
                                    # Create temporary variable for IP
                                    $TempIP = "127.0.0.1/32"
                                    # Apply appropriate prefix for IP version
                                    $AddressType = $vCenterIP | Select-Object -Property AddressFamily
                                    if ([String]$AddressType -eq "@{AddressFamily=InterNetwork}") {
                                        $TempIP = $IP + "/32"
                                    } elseif ([String]$AddressType -eq "@{AddressFamily=InterNetworkV6}") {
                                        $TempIP = $IP + "/128"
                                    } else {
                                        Write-Warning -Message [String]::Format("Address {0} is of type {1}, skipping...", $IP, $AddressType)
                                        continue
                                    }
                                    $IPs += $TempIP
                                }
            
                                $Interface = @{
                                    "enabled" = $NIC.Connected
                                    "addresses" = $IPs
                                    "name" = $NIC.Device.Name
                                    "mac_address" = $NIC.MACAddress
                                    "virtual_machine" = $NetboxID
                                }
                                $vCenterNICs += $Interface
                            }
                        }
                    }
                }
        
                # Retrieve info on NICs present in Netbox
                $URI = $URIBase + $InterfacesPath + "/?virtual_machine_id=$NetboxID"
                $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
                ConvertTo-JSON $Response | Write-Verbose
                $NetboxNICs = $Response.Results
        
                # 3 conditions we're interested in:
                # 1. Interface is in Netbox and not vCenter -> delete interface from Netbox
                # 2. Interface is in vCenter and not Netbox -> create new Netbox interface
                # 3. Interface is in both -> update info if necessary
        
                # create list of MACs for Netbox
                $NetboxMACs = @()
                foreach ($NetboxNIC in $NetboxNICs) {
                    $NetboxMACs += $NetboxNIC.mac_address
                }
                # create list of MACs for vCenter
                $vCenterMACs = @()
                foreach ($vCenterNIC in $vCenterNICs) {
                    $vCenterMACs += $vCenterNIC.mac_address
                }
                # Delete any interfaces in Netbox that are not present in vCenter
                foreach ($NetboxNIC in $NetboxNICs) {
                    $vCenterContains = $vCenterMACs -contains $NetboxNIC.mac_address
                    if (-Not $vCenterContains) {
                        # Netbox interface does not match vCenter's, so remove it
                        $Message = "Deleting Netbox interface " + $NetboxNIC.name
                        Write-Verbose $Message
                        $URI = $URIBase + $InterfacesPath + "/" + $NetboxNIC.id + "/"
                        $Response = Invoke-RESTMethod -Method DELETE -Headers $Headers -ContentType "application/json" -URI $URI
                        ConvertTo-JSON $Response | Write-Verbose
                    }
                }
                # create hashtable mapping Netbox interface IDs to IP lists as we process them
                $IPAssignments = @{}
                foreach ($vCenterNIC in $vCenterNICs) {
                    $NetboxContains = $NetboxMACs -contains $vCenterNIC.mac_address
                    if (-Not $NetboxContains) {
                        # Interface is in vCenter but not Netbox, so create new interface in Netbox with details from vCenter
                        $Message = "Creating Netbox interface " + $vCenterNIC.name
                        Write-Verbose $Message
                        $vCenterNICJSON = ConvertTo-JSON $vCenterNIC
                        $URI = $URIBase + $InterfacesPath + "/"
                        $Response = Invoke-RESTMethod -Method POST -Headers $Headers -ContentType "application/json" -Body $vCenterNICJSON -URI $URI
                        ConvertTo-JSON $Response | Write-Verbose
                        $NIC = $Response
                        # Store interface ID
                        $NICID = [String]$NIC.ID
                        # Get list of addresses from hash table and delete
                        $IPs = $vCenterNIC.addresses
                        $vCenterNIC.Remove["addresses"]
                        # store IP list in Netbox interface ID to IP arrary hashtable
                        $IPAssignments[$NICID] = $IPs
                    } else {
                        # NIC exists in both, now identify which
                        foreach ($NetboxNIC in $NetboxNICs) {
                            $Message = [String]::Format("Comparing Netbox interface '{0}' and vCenter interface '{1}'", $NetboxNIC.name, $vCenterNIC.name)
                            Write-Verbose $Message
                            if ($vCenterNIC.mac_address -eq $NetboxNIC.mac_address) {
                                # Interfaces match, so only need to update if necessary
                                $NICUpdate = @{}
                                # Store interface ID
                                $NICID = [String]$NetboxNIC.id
                                # Currently we don't want to overwrite any custom name (e.g. from Ansible or manual)
                                #If ($NetboxNIC.Name -ne $vCenterNIC.Name) { $NICUpdate["name"] = $vCenterNIC.Name }
                                if ($NetboxNIC.enabled -ne $vCenterNIC.enabled) { $NICUpdate["enabled"] = $vCenterNIC.enabled }
                                # Get list of addresses from hash table and delete
                                $IPs = $vCenterNIC.addresses
                                $vCenterNIC.Remove["addresses"]
                                # store IP list in Netbox interface ID to IP arrary hashtable
                                $IPAssignments[$NICID] = $IPs
                                if ($NICUpdate.count -gt 0) {
                                    # only want to patch if there is anything that needs to change
                                    $Message = "Updating Netbox interface " + $NetboxNIC.name
                                    Write-Verbose $Message
                                    $NICUpdateJSON = ConvertTo-JSON $NICUpdate
                                    $URI = $URIBase + $InterfacesPath + "/" + $NetboxNIC.id + "/"
                                    $Response = Invoke-RESTMethod -Method PATCH -Headers $Headers -ContentType "application/json" -Body $NICUpdateJSON -URI $URI
                                    ConvertTo-JSON $Response | Write-Verbose
                                }
                            } 
                        }
                    }
                }
        
                ConvertTo-JSON $IPAssignments | Write-Verbose
        
                # situations to consider:
                # 1. IP is assigned in Netbox and not configured in vCenter -> change IP status to "deprecated" in Netbox (just in case NIC was disabled, etc)
                # 2. IP is configured in vCenter and not present in Netbox -> create new Netbox IP and assign to Netbox interface
                # 3. IP is configured in both -> set to active in Netbox if it is not already and confirm interface
        
                # Create list of all IPs configured on vCenter VM
                $ConfiguredIPs = @()
                foreach ($InterfaceID in $IPAssignments.Keys) {
                    $ConfiguredIPs += $IPAssignments[$InterfaceID]
                }
        
                # Retrieve all IPs assigned to virtual machine in Netbox
                # helpful: https://groups.google.com/forum/#!topic/netbox-discuss/iREz7f9-bN0
                $URI = $URIBase + $IPAddressesPath + "/?virtual_machine_id=" + $NetboxID
                $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
                ConvertTo-JSON $Response | Write-Verbose
                $NetboxIPs = $Response.Results
        
                # iterate through and store results in array
                $AssignedIPs = @()
                foreach ($NetboxIP in $NetboxIPs) {
                    $IP = $NetboxIP.address
                    if ($ConfiguredIPs -contains $IP) {
                        # vCenter VM has IP configured, so keep it
                        $AssignedIPs += $IP.address
                    } else {
                        # IP assigned in Netbox but not configured in vCenter, so set to "deprecated"
                        $Date = Get-Date -Format d
                        $Description = [String]::Format("{0} - inactive {1}", $NetboxVM.Name, $Date)
                        $IPPatch = @{
                            "status" = "deprecated"
                            "description" = $Description
                        }
                        $IPPatchJSON = ConvertTo-JSON $IPPatch
                        $URI = $URIBase + $IPAddressesPath + "/" + $NetboxIP.id + "/"
                        $Response = Invoke-RESTMethod -Method PATCH -Headers $Headers -ContentType "application/json" -Body $IPPatchJSON -URI $URI
                        ConvertTo-JSON $Response | Write-Verbose
                    }
                }
        
                # create or update IPs for each interface as needed
                foreach ($InterfaceID in $IPAssignments.Keys) {
                    # get list of IPs from vCenter
                    $vCenterIPs = $IPAssignments[$InterfaceID]
                    # Iterate through this interfaces's IPs and check if they are configured in Netbox
                    foreach ($vCenterIP in $vCenterIPs) {
                        if ($AssignedIPs -notcontains $vCenterIP) {
                            # IP not assigned to VM in Netbox, but need to check if it exists already
                            $URI = $URIBase + $IPAddressesPath + "/?q=" + $vCenterIP
                            $Response = Invoke-RESTMethod -Method GET -Headers $Headers -ContentType "application/json" -URI $URI
                            ConvertTo-JSON $Response | Write-Verbose
                            if ($Response.count -gt 0) {
                                # IP exists in Netbox, need to assign it to Netbox VM
                                $NetboxIP = $Response.results
                                # create details for patching IP in Netbox
                                $Description = $NetboxVM.Name
                                $IPPatch = @{
                                    "status" = "active"
                                    "description" = $Description
                                    "vminterface" = $InterfaceID
                                }
                                $IPPatchJSON = ConvertTo-JSON $IPPatch
                                $URI = $URIBase + $IPAddressesPath + "/" + $NetboxIP.id + "/"
                                $Response = Invoke-RESTMethod -Method PATCH -Headers $Headers -ContentType "application/json" -Body $IPPatchJSON -URI $URI
                                ConvertTo-JSON $Response | Write-Verbose
                                $AssignedIPs += $NetboxIP.address
                            } else {
                                # IP does not exist in Netbox, so we need to create it
                                $Description = $NetboxVM.Name
                                $IPPost = @{
                                    "address" = $vCenterIP
                                    "status" = "active"
                                    "description" = $Description
                                    "vminterface" = $InterfaceID
                                }
                                $IPPostJSON = ConvertTo-JSON $IPPost
                                $URI = $URIBase + $IPAddressesPath + "/"
                                $Response = Invoke-RESTMethod -Method POST -Headers $Headers -ContentType "application/json" -Body $IPPostJSON -URI $URI
                                ConvertTo-JSON $Response | Write-Verbose
                                $AssignedIPs += $Response.address
                            }
                        } else {
                            # IP exists in Netbox, make sure status is "Active" and that the interface is correct
                            # Search through Netbox IPs to find corresponding IP
                            foreach ($NetboxIP in $NetboxIPs) {
                                if ($vCenterIP -eq $NetboxIP.address) {
                                    # we've found the corresponding entry so determine what data needs to be updated
                                    $IPPatch = @{}
                                    # check that the IP is on the correct interface
                                    if ($NetboxIP.interface -ne $InterfaceID) { $IPPatch["vminterface"] = $InterfaceID }
                                    # check that the status is active
                                    if ($NetboxIP.status -ne "active") { $IPPatch["status"] = "active" }
                                    # check that the description contains the hostname
                                    $VMShortName = $NetboxVM.Name.Split('.')[0]
                                    $DescriptionMatch = $NetboxIP.description -match $VMShortName
                                    if (-not $DescriptionMatch) {
                                        $IPPatch["status"] = "active"
                                    }
                                    # Only submit patches if anything has changed
                                    if ($IPPatch.count -gt 0) {
                                        $IPPatchJSON = ConvertTo-JSON $IPPatch
                                        $URI = $URIBase + $IPAddressesPath + "/" + $NetboxIP.id + "/"
                                        $Response = Invoke-RESTMethod -Method PATCH -Headers $Headers -ContentType "application/json" -Body $IPPatchJSON -URI $URI
                                        ConvertTo-JSON $Response | Write-Verbose
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    process {
    }
    
    end {
    }
}


#-----------------------------------------------------------[Execution]------------------------------------------------------------

# setup logging to file
$Date = Get-Date -UFormat "%Y-%m-%d"
$LogPath = "D:\logs\" + $Date + "_vcenter_netbox_sync.log"
Start-Transcript -Path $LogPath
# import the PowerCLI module
Import-Module VMware.PowerCLI
# Make sure that you are connected to the vCenter servers before running this manually
$Credential = Get-Credential
Connect-VIServer -Server vcenter.example.com -Credential $Credential

# If running as a scheduled task, ideally you can use a service account
# that can login to both Windows and vCenter with the account's Kerberos ticket
# In that case, you can remove the -Credential from the above Connect-VIServer call

# create your own token at your Netbox instance, e.g. https://netbox.example.com/user/api-tokens/
# You may need to assign addtional user permissions at https://netbox.example.com/admin/auth/user/
# since API permissions are not inherited from LDAP group permissions
$Token = "insert-token-generated-above"
Sync-Netbox -Token $Token
# If you want to see REST responses, add the Verbose flag
#Sync-Netbox -Verbose -Token $Token
Stop-Transcript
