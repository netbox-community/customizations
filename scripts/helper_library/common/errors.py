#!/usr/bin/python3

"""Custom Exceptions used in the NetBox scripts ."""

################################################################################
#                                 Exceptions                                   #
################################################################################


class InvalidInput(Exception):
    """Raised if we detected invalid input data."""

    pass


class NetBoxDataError(Exception):
    """Raised if something we expected to be there, doesn't exist."""

    pass
