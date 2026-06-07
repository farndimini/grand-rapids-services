$env:PORT = "8080"
$python = "C:\Users\pc\AppData\Local\Programs\Python\Python313\python.exe"
$script = "C:\Users\pc\Desktop\2026\New folder\New folder\AGENT 5\projects\grand_rapids\dev_server.py"

# Start server
$job = Start-Job -ScriptBlock { param($p, $s) & $p $s } -ArgumentList $python, $script
Start-Sleep -Seconds 5

# Test URLs
$tests = @(
    "/", "/hubs/appliance-repair-grand-rapids", "/authority/about-us",
    "/24-hour-appliance-repair-cascade-mi", "/appliance_repair_grand_rapids",
    "/about-us", "/emergency-appliance-repair-ada-mi",
    "/neighborhoods/appliance-repair-heritage-hill-grand-rapids",
    "/same-day-appliance-repair-grand-rapids-mi",
    "/affordable-appliance-repair-rockford-mi", "/near-me-appliance-repair-ada-mi",
    "/garage_door_repair_grand_rapids", "/shower_remodel_grand_rapids",
    "/basement_remodel_grand_rapids", "/sitemap/sitemap-index.xml",
    "/sitemap/sitemap-hubs.xml", "/sitemap/sitemap-index",
    "/contact", "/financing"
)

$allOk = $true
foreach ($t in $tests) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "http://localhost:8080$t" --max-time 5
    if ($code -eq "200") {
        Write-Host "OK  $t"
    } else {
        Write-Host "ERR $code $t"
        $allOk = $false
    }
}

Write-Host ""
if ($allOk) {
    Write-Host "ALL TESTS PASSED!"
} else {
    Write-Host "SOME TESTS FAILED!"
}

Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -Force -ErrorAction SilentlyContinue
