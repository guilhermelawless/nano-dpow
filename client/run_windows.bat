@echo off

:: Nano payout address
set payout_address="ban_1boompow14irck1yauquqypt7afqrh8b6bbu5r93pc6hgbqs7z6o99frcuym"

:: Desired work type, options are "ondemand", "precache", "any" (default)
set desired_work_type="any"

:: Optional delay before starting a BoomPow client
set start_delay_seconds=3

echo Starting PoW Service minimized...
start /min "PoW Service" cmd /c ".\bin\windows\nano-work-server.exe --gpu 1:0 -l 127.0.0.1:7000 && pause"

echo PoW Service started.
timeout %start_delay_seconds%

echo.
echo Starting BoomPow Client...
python bpow_client.py --payout %payout_address% --work %desired_work_type%

pause
