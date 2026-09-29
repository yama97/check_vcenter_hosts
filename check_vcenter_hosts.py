#!/usr/bin/env python3
#
# check_vcenter_hosts.py
#
# Nagios plugin for monitoring ESXi hosts managed by VMware vCenter.
#
# Copyright (c) 2026 Seiichi Yamamoto
# Licensed under the MIT License.
#
# Supported API modes:
#
#   --api rest
#       Legacy REST API
#       Tested with vCenter 6.5
#
#       POST   /rest/com/vmware/cis/session
#       GET    /rest/vcenter/host
#       DELETE /rest/com/vmware/cis/session
#
#   --api api
#       New API
#       Tested with vCenter 7
#
#       POST   /api/session
#       GET    /api/vcenter/host
#       DELETE /api/session
#
#   --api auto
#       Try the new API first, then the legacy REST API.
#
# Requirements:
#   Python 3 standard library only.
#
# Nagios return codes:
#   0 = OK
#   1 = WARNING
#   2 = CRITICAL
#   3 = UNKNOWN
#

import argparse
import base64
import json
import ssl
import sys
import urllib.error
import urllib.request


VERSION = "1.0.0"

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3


class APIError(Exception):
    """vCenter API access error."""
    pass


def nagios_exit(code, message, perfdata=None):
    """Print Nagios-compatible output and exit."""

    if perfdata:
        print(f"{message} | {perfdata}")
    else:
        print(message)

    sys.exit(code)


def load_credentials(filename):
    """Load username and password from a JSON file."""

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

    except Exception as e:
        nagios_exit(
            UNKNOWN,
            f"VCENTER UNKNOWN - "
            f"cannot read credential file: {e}"
        )

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        nagios_exit(
            UNKNOWN,
            "VCENTER UNKNOWN - "
            "username or password missing in credential file"
        )

    return username, password


def create_ssl_context(verify):
    """Create SSL context."""

    if verify:
        return ssl.create_default_context()

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    return context


def api_request(
    url,
    context,
    method="GET",
    headers=None,
    username=None,
    password=None,
    timeout=10
):
    """Send an HTTP request to the vCenter API."""

    if headers is None:
        headers = {}

    headers = dict(headers)

    if username is not None and password is not None:
        auth_string = f"{username}:{password}"

        auth_base64 = base64.b64encode(
            auth_string.encode("utf-8")
        ).decode("ascii")

        headers["Authorization"] = (
            f"Basic {auth_base64}"
        )

    request = urllib.request.Request(
        url,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(
            request,
            context=context,
            timeout=timeout
        ) as response:

            body = response.read().decode("utf-8")

            if not body:
                return None

            return json.loads(body)

    except urllib.error.HTTPError as e:
        raise APIError(
            f"HTTP error {e.code}: {e.reason}"
        )

    except urllib.error.URLError as e:
        raise APIError(
            f"connection failed: {e.reason}"
        )

    except TimeoutError:
        raise APIError(
            f"API timeout after {timeout} seconds"
        )

    except json.JSONDecodeError as e:
        raise APIError(
            f"invalid JSON response: {e}"
        )


#
# New API
# Tested with vCenter 7
#

def create_session_api(
    vcenter,
    username,
    password,
    context,
    timeout
):
    """Create a session using the new vCenter API."""

    url = f"https://{vcenter}/api/session"

    result = api_request(
        url,
        context,
        method="POST",
        username=username,
        password=password,
        timeout=timeout
    )

    # /api/session returns the session ID directly:
    #
    # "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    #
    if not isinstance(result, str) or not result:
        raise APIError(
            "unexpected response from /api/session"
        )

    return result


def get_hosts_api(
    vcenter,
    session_id,
    context,
    timeout
):
    """Get ESXi host list using the new vCenter API."""

    url = f"https://{vcenter}/api/vcenter/host"

    headers = {
        "vmware-api-session-id": session_id
    }

    result = api_request(
        url,
        context,
        method="GET",
        headers=headers,
        timeout=timeout
    )

    # /api/vcenter/host returns the list directly:
    #
    # [
    #   {
    #       "host": "...",
    #       "name": "...",
    #       "connection_state": "CONNECTED",
    #       "power_state": "POWERED_ON"
    #   }
    # ]
    #
    if not isinstance(result, list):
        raise APIError(
            "unexpected response from /api/vcenter/host"
        )

    return result


def delete_session_api(
    vcenter,
    session_id,
    context,
    timeout
):
    """Delete a session created using the new vCenter API."""

    url = f"https://{vcenter}/api/session"

    headers = {
        "vmware-api-session-id": session_id
    }

    try:
        api_request(
            url,
            context,
            method="DELETE",
            headers=headers,
            timeout=timeout
        )

    except Exception:
        # Session cleanup failure does not affect
        # the Nagios monitoring result.
        pass


#
# Legacy REST API
# Tested with vCenter 6.5
#

def create_session_rest(
    vcenter,
    username,
    password,
    context,
    timeout
):
    """Create a session using the legacy vCenter REST API."""

    url = (
        f"https://{vcenter}"
        "/rest/com/vmware/cis/session"
    )

    result = api_request(
        url,
        context,
        method="POST",
        username=username,
        password=password,
        timeout=timeout
    )

    # Legacy API response:
    #
    # {
    #     "value": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    # }
    #
    if (
        not isinstance(result, dict)
        or "value" not in result
        or not result["value"]
    ):
        raise APIError(
            "unexpected response from "
            "/rest/com/vmware/cis/session"
        )

    return result["value"]


def get_hosts_rest(
    vcenter,
    session_id,
    context,
    timeout
):
    """Get ESXi host list using the legacy vCenter REST API."""

    url = f"https://{vcenter}/rest/vcenter/host"

    headers = {
        "vmware-api-session-id": session_id
    }

    result = api_request(
        url,
        context,
        method="GET",
        headers=headers,
        timeout=timeout
    )

    # Legacy API response:
    #
    # {
    #     "value": [
    #         {
    #             "host": "...",
    #             "name": "...",
    #             "connection_state": "CONNECTED",
    #             "power_state": "POWERED_ON"
    #         }
    #     ]
    # }
    #
    if (
        not isinstance(result, dict)
        or "value" not in result
        or not isinstance(result["value"], list)
    ):
        raise APIError(
            "unexpected response from /rest/vcenter/host"
        )

    return result["value"]


def delete_session_rest(
    vcenter,
    session_id,
    context,
    timeout
):
    """Delete a session created using the legacy REST API."""

    url = (
        f"https://{vcenter}"
        "/rest/com/vmware/cis/session"
    )

    headers = {
        "vmware-api-session-id": session_id
    }

    try:
        api_request(
            url,
            context,
            method="DELETE",
            headers=headers,
            timeout=timeout
        )

    except Exception:
        # Session cleanup failure does not affect
        # the Nagios monitoring result.
        pass


def query_api(
    vcenter,
    username,
    password,
    context,
    timeout
):
    """Query vCenter using the new API."""

    session_id = None

    try:
        session_id = create_session_api(
            vcenter,
            username,
            password,
            context,
            timeout
        )

        hosts = get_hosts_api(
            vcenter,
            session_id,
            context,
            timeout
        )

        return hosts

    finally:
        if session_id:
            delete_session_api(
                vcenter,
                session_id,
                context,
                timeout
            )


def query_rest(
    vcenter,
    username,
    password,
    context,
    timeout
):
    """Query vCenter using the legacy REST API."""

    session_id = None

    try:
        session_id = create_session_rest(
            vcenter,
            username,
            password,
            context,
            timeout
        )

        hosts = get_hosts_rest(
            vcenter,
            session_id,
            context,
            timeout
        )

        return hosts

    finally:
        if session_id:
            delete_session_rest(
                vcenter,
                session_id,
                context,
                timeout
            )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Nagios plugin for monitoring ESXi hosts "
            "managed by VMware vCenter"
        )
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}"
    )

    parser.add_argument(
        "-H",
        "--host",
        required=True,
        help="vCenter hostname or IP address"
    )

    parser.add_argument(
        "-f",
        "--credential-file",
        required=True,
        help="JSON credential file"
    )

    parser.add_argument(
        "-e",
        "--expected",
        type=int,
        required=True,
        help="Expected number of ESXi hosts"
    )

    parser.add_argument(
        "--api",
        choices=["rest", "api", "auto"],
        default="auto",
        help=(
            "API type: "
            "rest=legacy REST API (vCenter 6.5), "
            "api=new API (vCenter 7+), "
            "auto=automatic detection "
            "(default: auto)"
        )
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=10,
        help="API timeout in seconds (default: 10)"
    )

    parser.add_argument(
        "--verify-cert",
        action="store_true",
        help="Verify vCenter TLS certificate"
    )

    args = parser.parse_args()

    if args.expected < 0:
        nagios_exit(
            UNKNOWN,
            "VCENTER UNKNOWN - "
            "expected host count cannot be negative"
        )

    if args.timeout <= 0:
        nagios_exit(
            UNKNOWN,
            "VCENTER UNKNOWN - "
            "timeout must be greater than zero"
        )

    username, password = load_credentials(
        args.credential_file
    )

    context = create_ssl_context(
        args.verify_cert
    )

    hosts = None
    api_used = None

    #
    # Explicit new API
    #
    if args.api == "api":
        try:
            hosts = query_api(
                args.host,
                username,
                password,
                context,
                args.timeout
            )

            api_used = "api"

        except APIError as e:
            nagios_exit(
                CRITICAL,
                f"VCENTER CRITICAL - API error: {e}"
            )

    #
    # Explicit legacy REST API
    #
    elif args.api == "rest":
        try:
            hosts = query_rest(
                args.host,
                username,
                password,
                context,
                args.timeout
            )

            api_used = "rest"

        except APIError as e:
            nagios_exit(
                CRITICAL,
                f"VCENTER CRITICAL - REST API error: {e}"
            )

    #
    # Automatic detection
    #
    else:
        api_error = None
        rest_error = None

        try:
            hosts = query_api(
                args.host,
                username,
                password,
                context,
                args.timeout
            )

            api_used = "api"

        except APIError as e:
            api_error = str(e)

        if hosts is None:
            try:
                hosts = query_rest(
                    args.host,
                    username,
                    password,
                    context,
                    args.timeout
                )

                api_used = "rest"

            except APIError as e:
                rest_error = str(e)

        if hosts is None:
            nagios_exit(
                CRITICAL,
                "VCENTER CRITICAL - "
                "both API methods failed; "
                f"api=[{api_error}], "
                f"rest=[{rest_error}]"
            )

    #
    # Evaluate ESXi host status
    #

    total = len(hosts)

    connected = 0
    powered_on = 0
    healthy = 0

    problems = []

    for host in hosts:

        if not isinstance(host, dict):
            problems.append(
                "unknown(INVALID_HOST_DATA)"
            )
            continue

        name = host.get(
            "name",
            "unknown"
        )

        connection_state = host.get(
            "connection_state",
            "UNKNOWN"
        )

        power_state = host.get(
            "power_state",
            "UNKNOWN"
        )

        if connection_state == "CONNECTED":
            connected += 1

        if power_state == "POWERED_ON":
            powered_on += 1

        if (
            connection_state == "CONNECTED"
            and power_state == "POWERED_ON"
        ):
            healthy += 1

        else:
            problems.append(
                f"{name}"
                f"({connection_state},{power_state})"
            )

    #
    # Nagios performance data
    #

    perfdata = (
        f"'hosts_total'={total} "
        f"'hosts_connected'={connected} "
        f"'hosts_powered_on'={powered_on} "
        f"'hosts_ok'={healthy}"
    )

    #
    # Registered host count differs from expected.
    #

    if total != args.expected:

        detail = ""

        if problems:
            detail = "; " + ", ".join(problems)

        nagios_exit(
            CRITICAL,
            f"VCENTER CRITICAL - "
            f"{total} hosts registered, "
            f"expected {args.expected}; "
            f"{connected} connected, "
            f"{powered_on} powered on; "
            f"api={api_used}"
            f"{detail}",
            perfdata
        )

    #
    # One or more registered hosts are not healthy.
    #

    if problems:
        nagios_exit(
            CRITICAL,
            f"VCENTER CRITICAL - "
            f"{healthy}/{total} hosts OK; "
            f"api={api_used}; "
            + ", ".join(problems),
            perfdata
        )

    #
    # Everything is healthy.
    #

    nagios_exit(
        OK,
        f"VCENTER OK - "
        f"{healthy}/{total} hosts "
        f"connected and powered on; "
        f"api={api_used}",
        perfdata
    )


if __name__ == "__main__":
    main()