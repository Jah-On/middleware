#
# /etc/pam.d/common-session - session-related modules common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of modules that define tasks to be performed
# at the start and end of sessions of *any* kind (both interactive and
# non-interactive).

<%namespace name="pam" file="pam.inc.mako" />\
<%
        dsp = pam.getDirectoryServicePam(middleware=middleware, render_ctx=render_ctx)
%>\

@include common-session-unix-header

% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_session()}
% endif

@include common-session-unix-footer
