$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

try {
    $commands = @('Get-NetFirewallProfile', 'Get-NetConnectionProfile', 'Get-NetFirewallRule',
        'Get-NetFirewallPortFilter', 'Get-NetFirewallAddressFilter',
        'Get-NetFirewallApplicationFilter', 'Get-NetFirewallServiceFilter')
    foreach ($command in $commands) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
            [Console]::Error.WriteLine('FIREWALL_UNAVAILABLE')
            exit 1
        }
    }
    $profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore | ForEach-Object {
        [ordered]@{
            name = $_.Name.ToString()
            enabled = ($_.Enabled.ToString() -eq 'True')
            default_inbound_action = $_.DefaultInboundAction.ToString()
            default_outbound_action = $_.DefaultOutboundAction.ToString()
        }
    })
    $active = @(Get-NetConnectionProfile | ForEach-Object {
        $category = $_.NetworkCategory.ToString()
        if ($category -eq 'DomainAuthenticated') { 'Domain' } else { $category }
    })
    $enabledRules = @(Get-NetFirewallRule -PolicyStore ActiveStore -TracePolicyStore | Where-Object {
        $_.Enabled.ToString() -eq 'True'
    })
    $filters = @{}
    foreach ($kind in @('Port', 'Address', 'Application', 'Service')) {
        $map = @{}
        if ($enabledRules.Count -gt 0) {
            $enabledRules | & "Get-NetFirewall${kind}Filter" | ForEach-Object {
                $map[$_.InstanceID] = $_
            }
        }
        $filters[$kind] = $map
    }
    $rules = @($enabledRules | ForEach-Object {
        $rule = $_
        foreach ($kind in @('Port', 'Address', 'Application', 'Service')) {
            if (-not $filters[$kind].ContainsKey($rule.Name)) {
                throw 'Missing firewall filter; retry the scan.'
            }
        }
        $port = $filters.Port[$rule.Name]
        $address = $filters.Address[$rule.Name]
        [ordered]@{
            name = $rule.Name
            display_name = $rule.DisplayName
            profiles = @($rule.Profile.ToString() -split ',\s*')
            direction = $rule.Direction.ToString()
            action = $rule.Action.ToString()
            protocol = $port.Protocol.ToString()
            local_ports = @($port.LocalPort | ForEach-Object { $_.ToString() })
            remote_ports = @($port.RemotePort | ForEach-Object { $_.ToString() })
            local_addresses = @($address.LocalAddress | ForEach-Object { $_.ToString() })
            remote_addresses = @($address.RemoteAddress | ForEach-Object { $_.ToString() })
            program = $filters.Application[$rule.Name].Program
            service = $filters.Service[$rule.Name].Service
            policy_source = $rule.PolicyStoreSource
        }
    })
    [ordered]@{ profiles = $profiles; active_profiles = $active; rules = $rules } |
        ConvertTo-Json -Depth 6 -Compress
} catch {
    if ($_.CategoryInfo.Category -eq 'PermissionDenied' -or
        $_.Exception -is [System.UnauthorizedAccessException] -or
        $_.FullyQualifiedErrorId -match 'AccessDenied|0x80070005') {
        [Console]::Error.WriteLine('FIREWALL_PERMISSION_DENIED')
    } else {
        [Console]::Error.WriteLine('FIREWALL_QUERY_FAILED')
    }
    exit 1
}
