@echo off


:: Nano payout address
set payout_address="nano_1dpowzkw9u6annz4z48aixw6oegeqicpozaajtcnjom3tqa3nwrkgsk6twj7"

:: Desired work type, options are "ondemand", "precache", "any" (default)
set desired_work_type="any"

:: Optional delay before starting a DPoW client
set start_delay_seconds=3




IF NOT "%1" == "-noserver" (
	echo Starting PoW Service minimized...
	start /min "PoW Service" cmd /c ".\bin\windows\nano-work-server.exe --gpu 1:0 -l 127.0.0.1:7000 && pause"
	echo PoW Service started.
)

timeout %start_delay_seconds%

echo.
echo Starting DPoW Client...
python dpow_client.py --payout %payout_address% --work %desired_work_type%

pause
