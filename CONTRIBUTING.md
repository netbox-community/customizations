# Contributing

## Getting Help

If you encounter any issues installing or using any of these scripts or reports, try one of the
following resources to get assistance. Please **do not** open a GitHub issue
except to report bugs or submit script/report ideas for the community to take up.

### GitHub Discussions

GitHub's discussions are the best place to get help with an existing script, propose rough ideas for
new functionality that you are trying to draft, or help creating your own script. Their integration
with GitHub allows for easily cross-referencing and converting posts to issues as needed. There are several
categories for discussions:

* **General** - General community discussion
* **Ideas** - Ideas for new functionality that isn't yet ready for a formal
  feature request
* **Q&A** - Request help with installing or using NetBox

### Slack

For real-time chat, you can join the **#netbox** Slack channel on [NetDev Community](https://netdev.chat/).
Unfortunately, the Slack channel does not provide long-term retention of chat
history, so try to avoid it for any discussions would benefit from being
preserved for future reference.

## Reporting Bugs

* First, check that you are running the version the report or script states it supports in the source file.

* Next, check the GitHub [issues list](https://github.com/netbox-community/reports/issues)
to see if the bug you've found has already been reported. If you think you may
be experiencing a reported issue that hasn't already been resolved, please
click "add a reaction" in the top right corner of the issue and add a thumbs
up (+1). You might also want to add a comment describing how it's affecting your
installation. This will allow us to prioritize bugs based on how many users are
affected.

* When submitting an issue, please be as descriptive as possible. Be sure to
provide all information request in the issue template, including:

  * The environment (NetBox version, deployment method, & Python Version) in which NetBox is running
  * The exact steps that can be taken to reproduce the issue
  * Expected and observed behavior
  * Any error messages generated
  * Screenshots (if applicable)

* Keep in mind that this is a community crowdsourced report, and maintainers are not
commiting to update or fix scripts submitted to the repo.  We will try out best to help
and update submitted scripts.

## Feature Requests

* First, check the GitHub [issues list](https://github.com/netbox-community/reports/issues)
to see if the feature you're requesting is already listed. (Be sure to search
closed issues as well, since some feature requests have been rejected.) If the
feature you'd like to see has already been requested and is open, click "add a
reaction" in the top right corner of the issue and add a thumbs up (+1). This
ensures that the issue has a better chance of receiving attention. Also feel
free to add a comment with any additional justification for the feature.
(However, note that comments with no substance other than a "+1" will be
deleted. Please use GitHub's reactions feature to indicate your support.)

* Before filing a new feature request, consider raising your idea in a
[GitHub discussion](https://github.com/netbox-community/netbox/discussions)
first. Feedback you receive there will help validate and shape the proposed
feature before filing a formal issue.

* Good feature requests are very narrowly defined. Be sure to thoroughly
describe the functionality and data model(s) being proposed. The more effort
you put into writing a feature request, the better its chance is of being
implemented. Overly broad feature requests will be closed.

* When submitting a feature request on GitHub, be sure to include all
information requested by the issue template, including:

  * A detailed description of the proposed functionality
  * A use case for the feature; who would use it and what value it would add
    to NetBox
  * A rough description of changes necessary to the database schema (if
    applicable)
  * Any third-party libraries or other resources which would be involved

* For more information on how feature requests are handled, please see our
[issue intake policy](https://github.com/netbox-community/netbox/wiki/Issue-Intake-Policy).

## Submitting Pull Requests

* If you're interested in contributing to this repo, be sure to check out our
[getting started](https://netbox.readthedocs.io/en/stable/development/getting-started/)
documentation for tips on setting up your development environment.

* Be sure to open an issue **before** starting work on a pull request, and
discuss your idea with the community before beginning work. This will
help prevent wasting time on something that might you might not be able to
implement. When suggesting a new feature, also make sure it won't conflict with
any work that's already in progress.

* Once you've opened or identified an issue you'd like to work on, ask that it
be assigned to you so that others are aware it's being worked on.

* Any pull request which does _not_ relate to an opened issue will be closed.

* Any pull request that duplicates functionality from an existing script or report
will be asked to redirect their functionality updates to the existing script/report.

* All new functionality must include relevant tests where applicable.

* All code submissions should meet the following criteria (CI will enforce
these checks):

  * Python syntax is valid
  * Black compliance is enforced
  * PEP 8 compliance is enforced, with the exception that lines may be
    greater than 80 characters in length

## Commenting

Only comment on an issue if you are sharing a relevant idea or constructive
feedback. **Do not** comment on an issue just to show your support (give the
top post a :+1: instead) or ask for an ETA. These comments will be deleted to
reduce noise in the discussion.

## Maintainer Guidance

* Maintainers are expected to help review Pull Request submissions, assist in
  troubleshooting PR test failures, and handle general project housekeeping.
  This can be employer-sponsored or individual time, with the understanding that
  all contributions are submitted under the Apache 2.0 license and that your
  employer may not make claim to any contributions. Contributions include code
  work, issue management, and community support.
