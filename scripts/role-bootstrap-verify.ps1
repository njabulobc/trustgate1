# TrustGate role bootstrap + verification script (PowerShell)
# - Creates one user per role (if not already present)
# - Verifies login and /auth/me for each
# - Skips existing users (409 conflict)

$ErrorActionPreference = "Stop"
$BaseUrl = "http://localhost:8000"

# Seeded admin credentials from backend defaults
$AdminUsername = "admin"
$AdminPassword = "admin123!"

# Test users to create/verify
$RoleUsers = @(
    @{ username = "admin2";      email = "admin2@trustgate.local";      full_name = "Admin Two";              role = "administrator";      password = "Passw0rd!" },
    @{ username = "compliance1"; email = "compliance1@trustgate.local"; full_name = "Compliance Officer One"; role = "compliance_officer"; password = "Passw0rd!" },
    @{ username = "analyst1";    email = "analyst1@trustgate.local";    full_name = "Analyst One";            role = "analyst";            password = "Passw0rd!" },
    @{ username = "reviewer1";   email = "reviewer1@trustgate.local";   full_name = "Reviewer One";           role = "reviewer";           password = "Passw0rd!" },
    @{ username = "auditor1";    email = "auditor1@trustgate.local";    full_name = "Auditor One";            role = "auditor";            password = "Passw0rd!" }
)

function Invoke-JsonRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [object]$Body = $null,
        [hashtable]$Headers = $null
    )

    try {
        if ($null -ne $Body) {
            return Invoke-RestMethod -Method $Method -Uri $Uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10) -Headers $Headers
        }

        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers
    }
    catch {
        $statusCode = $null
        $rawBody = $null

        if ($_.Exception.Response) {
            try { $statusCode = [int]$_.Exception.Response.StatusCode } catch {}
            try {
                $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $rawBody = $sr.ReadToEnd()
                $sr.Close()
            }
            catch {}
        }

        return [pscustomobject]@{
            __error = $true
            StatusCode = $statusCode
            RawBody = $rawBody
            Message = $_.Exception.Message
        }
    }
}

Write-Host "== TrustGate role setup and verification ==" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl"

# 1) Admin login
$adminLogin = Invoke-JsonRequest -Method "Post" -Uri "$BaseUrl/auth/login" -Body @{
    username = $AdminUsername
    password = $AdminPassword
}

if ($adminLogin.__error) {
    Write-Host "❌ Admin login failed. Check API is running and seeded admin credentials are correct." -ForegroundColor Red
    Write-Host "   Status: $($adminLogin.StatusCode)  Body: $($adminLogin.RawBody)"
    return
}

$adminToken = $adminLogin.access_token
$adminHeaders = @{ Authorization = "Bearer $adminToken" }

Write-Host "✅ Admin login succeeded as '$($adminLogin.user.username)' (role=$($adminLogin.user.role))" -ForegroundColor Green

# 2) Create users if needed
Write-Host "`n-- Creating users (skip if already exists) --" -ForegroundColor Yellow
foreach ($u in $RoleUsers) {
    $createResp = Invoke-JsonRequest -Method "Post" -Uri "$BaseUrl/auth/users" -Headers $adminHeaders -Body @{
        username = $u.username
        email = $u.email
        full_name = $u.full_name
        role = $u.role
        password = $u.password
    }

    if ($createResp.__error) {
        if ($createResp.StatusCode -eq 409) {
            Write-Host "⚠️  Skipped '$($u.username)' ($($u.role)) - already exists." -ForegroundColor DarkYellow
        }
        elseif ($createResp.StatusCode -eq 403 -or $createResp.StatusCode -eq 401) {
            Write-Host "❌ Not authorized creating '$($u.username)'. Admin token/role issue." -ForegroundColor Red
            Write-Host "   Status: $($createResp.StatusCode)  Body: $($createResp.RawBody)"
        }
        else {
            Write-Host "❌ Failed to create '$($u.username)' ($($u.role))." -ForegroundColor Red
            Write-Host "   Status: $($createResp.StatusCode)  Body: $($createResp.RawBody)"
        }
    }
    else {
        Write-Host "✅ Created '$($createResp.username)' (role=$($createResp.role))." -ForegroundColor Green
    }
}

# 3) Verify each role login + /auth/me
Write-Host "`n-- Verifying each role (login + /auth/me + capabilities) --" -ForegroundColor Yellow
$summary = @()

foreach ($u in $RoleUsers) {
    $loginResp = Invoke-JsonRequest -Method "Post" -Uri "$BaseUrl/auth/login" -Body @{
        username = $u.username
        password = $u.password
    }

    if ($loginResp.__error) {
        Write-Host "❌ Login failed for '$($u.username)' expected role '$($u.role)'." -ForegroundColor Red
        Write-Host "   Status: $($loginResp.StatusCode)  Body: $($loginResp.RawBody)"
        $summary += [pscustomobject]@{
            Username = $u.username
            ExpectedRole = $u.role
            Login = "FAIL"
            RoleMatch = "N/A"
            CapabilitiesCount = 0
            MeCheck = "FAIL"
        }
        continue
    }

    $userRole = $loginResp.user.role
    $caps = @($loginResp.user.capabilities)
    $roleMatch = ($userRole -eq $u.role)

    $userHeaders = @{ Authorization = "Bearer $($loginResp.access_token)" }
    $meResp = Invoke-JsonRequest -Method "Get" -Uri "$BaseUrl/auth/me" -Headers $userHeaders

    $meCheck = "FAIL"
    if (-not $meResp.__error) {
        $meCheck = if ($meResp.username -eq $u.username -and $meResp.role -eq $u.role) { "PASS" } else { "MISMATCH" }
    }

    if ($roleMatch -and $meCheck -eq "PASS") {
        Write-Host "✅ $($u.username): login OK, role=$userRole, capabilities=$($caps.Count), /me OK" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  $($u.username): login role=$userRole (expected $($u.role)), /me=$meCheck, capabilities=$($caps.Count)" -ForegroundColor DarkYellow
    }

    $summary += [pscustomobject]@{
        Username = $u.username
        ExpectedRole = $u.role
        Login = "PASS"
        RoleMatch = if ($roleMatch) { "PASS" } else { "FAIL" }
        CapabilitiesCount = $caps.Count
        MeCheck = $meCheck
    }
}

Write-Host "`n== Summary ==" -ForegroundColor Cyan
$summary | Format-Table -AutoSize

Write-Host "`nDone." -ForegroundColor Cyan
