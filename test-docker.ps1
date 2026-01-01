# Docker Network Test Script for PowerShell
Write-Host " Testing Docker P2P Network..." -ForegroundColor Cyan

# 1. Clean up
Write-Host "`n1. Cleaning up..." -ForegroundColor Yellow
docker-compose down 2>$null

# 2. Build
Write-Host "`n2. Building containers..." -ForegroundColor Yellow
docker-compose build

# 3. Start services
Write-Host "`n3. Starting services..." -ForegroundColor Yellow
docker-compose up -d

# 4. Wait
Write-Host "`n4. Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# 5. Check status
Write-Host "`n5. Checking status:" -ForegroundColor Green
docker-compose ps

# 6. Test STUN server
Write-Host "`n6. Testing STUN server:" -ForegroundColor Green
docker exec p2p-stun-server curl -s http://localhost:8000/health

# 7. Test peer1 connectivity
Write-Host "`n7. Testing peer1 connectivity:" -ForegroundColor Green
docker exec p2p-peer-1 curl -s http://stun-server:8000/health

# 8. Create test file in peer1
Write-Host "`n8. Creating test file..." -ForegroundColor Green
docker exec p2p-peer-1 sh -c "echo 'Test from Docker P2P' > /app/test.txt"

Write-Host "`n Test setup complete!" -ForegroundColor Green
Write-Host "`n Next steps:" -ForegroundColor Cyan
Write-Host "   1. docker attach p2p-peer-1" -ForegroundColor White
Write-Host "   2. docker attach p2p-peer-2" -ForegroundColor White
Write-Host "   3. Test chat and file transfer" -ForegroundColor White
