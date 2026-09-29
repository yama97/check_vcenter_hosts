# check_vcenter_hosts

A Nagios plugin for monitoring ESXi hosts managed by VMware vCenter.

The plugin connects to the vCenter API and checks:

- Number of ESXi hosts registered in vCenter
- ESXi host connection state
- ESXi host power state
- Overall host health

The plugin uses only the Python 3 standard library. No additional Python packages are required.

## Features

- Nagios-compatible return codes
- Checks expected number of ESXi hosts
- Checks whether all ESXi hosts are `CONNECTED`
- Checks whether all ESXi hosts are `POWERED_ON`
- Nagios performance data output
- Supports legacy and current vCenter REST APIs
- No external Python modules required

## Requirements

- Python 3
- VMware vCenter
- Nagios Core or another monitoring system compatible with Nagios plugins

## API Support

| vCenter | API mode | API endpoint | Status |
|---|---|---|---|
| vCenter 6.5 | `rest` | `/rest/...` | Tested |
| vCenter 7 | `api` | `/api/...` | Tested |
| vCenter 8 | `api` | `/api/...` | Same API endpoints |
| Other versions | `auto` | Automatic detection | Available |

The following API modes can be selected:

- `--api rest` - Legacy REST API
- `--api api` - Current vCenter API
- `--api auto` - Try the current API first, then the legacy REST API

For production monitoring, explicitly specifying `rest` or `api` is recommended.

## Installation

Copy the plugin to the Nagios local plugin directory:

~~~bash
sudo mkdir -p /usr/local/lib/nagios/plugins

sudo cp check_vcenter_hosts.py \
    /usr/local/lib/nagios/plugins/

sudo chmod 755 \
    /usr/local/lib/nagios/plugins/check_vcenter_hosts.py
~~~

## Credential File

Create a JSON credential file.

Example:

~~~json
{
    "username": "administrator@example.local",
    "password": "PASSWORD"
}
~~~

For example, save it as:

~~~text
/etc/nagios4/private/vcenter.json
~~~

Set appropriate permissions:

~~~bash
sudo chown root:nagios /etc/nagios4/private/vcenter.json
sudo chmod 640 /etc/nagios4/private/vcenter.json
~~~

Do not commit the actual credential file to a Git repository.

An example credential file can be stored in the repository as:

~~~text
vcenter.json.example
~~~

## Usage

General syntax:

~~~bash
./check_vcenter_hosts.py \
    -H VCENTER \
    -f CREDENTIAL_FILE \
    -e EXPECTED_HOSTS \
    --api API_MODE
~~~

### vCenter 6.5

Use the legacy REST API:

~~~bash
./check_vcenter_hosts.py \
    -H vcenter.example.com \
    -f ./vcenter.json \
    -e 10 \
    --api rest
~~~

### vCenter 7 or 8

Use the current API:

~~~bash
./check_vcenter_hosts.py \
    -H vcenter.example.com \
    -f ./vcenter.json \
    -e 5 \
    --api api
~~~

### Automatic API Detection

The plugin can automatically try both API types:

~~~bash
./check_vcenter_hosts.py \
    -H vcenter.example.com \
    -f ./vcenter.json \
    -e 5 \
    --api auto
~~~

`auto` is the default API mode, so the following is equivalent:

~~~bash
./check_vcenter_hosts.py \
    -H vcenter.example.com \
    -f ./vcenter.json \
    -e 5
~~~

## Example Output

Normal operation:

~~~text
VCENTER OK - 5/5 hosts connected and powered on; api=api | 'hosts_total'=5 'hosts_connected'=5 'hosts_powered_on'=5 'hosts_ok'=5
~~~

If the expected host count is 6 but only 5 hosts are registered:

~~~text
VCENTER CRITICAL - 5 hosts registered, expected 6; 5 connected, 5 powered on; api=api | 'hosts_total'=5 'hosts_connected'=5 'hosts_powered_on'=5 'hosts_ok'=5
~~~

If one or more ESXi hosts are not connected or powered on, the plugin returns CRITICAL and includes the affected host names and states.

## Command Line Options

~~~text
-H, --host
    vCenter hostname or IP address

-f, --credential-file
    JSON file containing the username and password

-e, --expected
    Expected number of ESXi hosts

--api {rest,api,auto}
    vCenter API mode

    rest : Legacy REST API
    api  : Current vCenter API
    auto : Automatic detection

-t, --timeout
    API timeout in seconds
    Default: 10

--verify-cert
    Enable TLS certificate verification
~~~

## Nagios Configuration

Example Nagios command definition:

~~~text
define command {
    command_name    check_vcenter_hosts
    command_line    /usr/local/lib/nagios/plugins/check_vcenter_hosts.py -H '$HOSTADDRESS$' -f /etc/nagios4/private/vcenter.json -e '$ARG1$' --api '$ARG2$'
}
~~~

Example service definition for five ESXi hosts using the current API:

~~~text
define service {
    use                     generic-service
    host_name               vcenter
    service_description     vCenter ESXi Host Status
    check_command           check_vcenter_hosts!5!api
    check_interval          5
    retry_interval          1
    max_check_attempts      3
}
~~~

For vCenter 6.5 using the legacy REST API:

~~~text
check_command check_vcenter_hosts!10!rest
~~~

## Nagios Return Codes

| Code | State | Meaning |
|---|---|---|
| 0 | OK | All expected ESXi hosts are connected and powered on |
| 1 | WARNING | Reserved |
| 2 | CRITICAL | Host count mismatch, unhealthy host, or API failure |
| 3 | UNKNOWN | Invalid configuration or unexpected response |

## Performance Data

The plugin outputs the following Nagios performance data:

~~~text
hosts_total
hosts_connected
hosts_powered_on
hosts_ok
~~~

Example:

~~~text
'hosts_total'=5 'hosts_connected'=5 'hosts_powered_on'=5 'hosts_ok'=5
~~~

## TLS Certificate Verification

By default, TLS certificate verification is disabled to support vCenter installations using self-signed certificates.

To enable certificate verification:

~~~bash
./check_vcenter_hosts.py \
    -H vcenter.example.com \
    -f ./vcenter.json \
    -e 5 \
    --api api \
    --verify-cert
~~~

The monitoring server must trust the certificate presented by vCenter when this option is enabled.

## Security

The credential file contains a vCenter username and password.

Recommended permissions:

~~~text
owner: root
group: nagios
mode: 0640
~~~

Do not store real credentials in the Git repository.

Add the credential filename to `.gitignore`:

~~~text
vcenter.json
~~~

## Tested Environments

The plugin has been tested with:

- VMware vCenter 6.5 using the legacy `/rest` API
- VMware vCenter 7 using the `/api` API
- Python 3
- Nagios Core 4

vCenter 8 uses the same `/api/session` and `/api/vcenter/host` API style used by the `api` mode, but should be considered separately from the versions explicitly tested above.

## License

Add the license for this project here.