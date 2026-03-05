# Elion MDM - QA Testing Plan

Plano abrangente de testes para todas plataformas antes de release para produção.

---

## 📋 Test Environments

```
┌──────────────────┬──────────────────┬─────────────┐
│ Environment      │ Configuration    │ Purpose     │
├──────────────────┼──────────────────┼─────────────┤
│ Development      │ localhost:8000   │ Feature dev │
│ Staging          │ staging.api      │ Pre-prod    │
│ Production       │ api.example.com  │ Live users  │
└──────────────────┴──────────────────┴─────────────┘
```

---

## 🔍 Backend Tests (Python/FastAPI)

### API Endpoint Tests

#### 1. Authentication Endpoints

| Test | Method | Endpoint | Expected |
|------|--------|----------|----------|
| User Registration | POST | `/api/auth/register` | 200 OK + user_id |
| User Login | POST | `/api/auth/login` | 200 OK + access_token |
| Token Refresh | POST | `/api/auth/refresh` | 200 OK + new_token |
| Invalid Login | POST | `/api/auth/login` | 401 Unauthorized |
| Expired Token | GET | `/api/devices` | 401 Unauthorized |

**Test Scripts:**
```bash
# Register admin
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"SecurePass123!"}'

# Expected: {"user_id": "123", "email": "admin@example.com"}
```

#### 2. Device Management Endpoints

| Test | Method | Endpoint | Check |
|------|--------|----------|-------|
| List Devices | GET | `/api/devices` | Returns array |
| Get Device Detail | GET | `/api/devices/{id}` | Device data matches |
| Deregister Device | DELETE | `/api/devices/{id}` | Device removed |
| Device Not Found | GET | `/api/devices/invalid-id` | 404 Not Found |

---

#### 3. Command Execution Endpoints

| Test | Scenario | Expected |
|------|----------|----------|
| Reboot Command | POST `/api/commands/reboot` | Command queued |
| Command Status | GET `/api/commands/{id}/status` | Status updates |
| Cancel Command | DELETE `/api/commands/{id}` | Command removed |
| Invalid Command | POST with bad type | 400 Bad Request |

---

#### 4. Telemetry Collection

| Test | Method | Expected |
|-------|--------|----------|
| Submit Telemetry | POST `/api/telemetry/check-in` | Data stored |
| Retrieve Telemetry | GET `/api/telemetry/device/{id}` | Latest data returned |
| Batch Telemetry | POST with 100 records | All stored correctly |
| Data Validation | POST with missing fields | 400 Bad Request |

**Sample Check-in Request:**
```json
{
  "device_id": "uuid-123",
  "battery_level": 85.5,
  "is_charging": true,
  "free_disk_space_mb": 2048,
  "installed_apps": ["com.example.app"],
  "latitude": 40.7128,
  "longitude": -74.0060,
  "foreground_app": "com.example.app",
  "daily_usage_stats": {"com.example.app": 3600000}
}
```

---

### Database Tests

#### Schema Validation

```bash
# Verificar todas as tables existem
psql -U mdm_user -d mdm_db -c "\dt"

# Esperado:
# users
# devices
# policies
# commands
# telemetry
# admin_audit_log
```

#### Data Integrity

```sql
-- Verificar foreign keys
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'telemetry';

-- Verificar índices para query performance
SELECT indexname FROM pg_indexes WHERE tablename = 'telemetry';
```

#### Migration Tests

```bash
# Executar migrations
python pg_migrate.py upgrade

# Verificar schema
psql -U mdm_user -d mdm_db -c "SELECT version FROM alembic_version;"
```

---

### Performance Tests

#### API Response Times

```bash
# Benchmark 100 requests
ab -n 100 -c 10 http://localhost:8000/api/devices

# Expected: Median response < 200ms
```

#### Database Query Performance

```sql
-- Verificar query execution time
EXPLAIN ANALYZE SELECT * FROM telemetry WHERE device_id = 'uuid-123' ORDER BY timestamp DESC LIMIT 10;

-- Expected: < 10ms
```

#### Load Testing

```bash
# Com 100 concurrent users
ab -n 10000 -c 100 http://localhost:8000/api/telemetry/check-in

# Expected: 0% errors, avg response < 500ms
```

---

## 📱 Android Tests

### Unit Tests

Run:
```bash
cd android/
./gradlew test
```

**Coverage Target:** >70% de linhas críticas

Verifying Tests:
```bash
./gradlew test --info
# Verificar saída para erros
```

---

### Instrumentation Tests

Run:
```bash
./gradlew connectedAndroidTest  # Device conectado
./gradlew connectedCheck         # Também roda unit tests
```

**Tests Inclusos:**
- MainActivity permission flow
- MDMService lifecycle
- API integration
- WorkManager task execution

---

### Manual Testing - Device Owner Setup

#### Prerequisites
- Android device com Android 10+
- Developer mode habilitado
- USB debugging ativo

#### Test Steps

**1. Provisioning via ADB**
```bash
# 1a. Instalar APK
adb install -r app/build/outputs/apk/debug/app-debug.apk

# 1b. Set as device owner
adb shell dpm set-device-owner com.example.androidmdm/.ElionAdminReceiver

# 1c. Verificar
adb shell dpm get-device-owner
# Esperado: com.example.androidmdm/.ElionAdminReceiver

# 1d. Grant permissions
adb shell pm grant com.example.androidmdm android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.example.androidmdm android.permission.SYSTEM_ALERT_WINDOW
adb shell pm grant com.example.androidmdm android.permission.PACKAGE_USAGE_STATS
```

**Test Case:** Enrollment Status
```
[ ] App inicia sem crash
[ ] 3 permissions visíveis
[ ] Permissions podem ser concedidas
[ ] Status muda para "Completed"
[ ] MDMService inicia automaticamente
```

**2. Check-in Functionality**
```bash
# Forçar immediate check-in
adb shell am startservice com.example.androidmdm/.MDMService

# Monitorar logs
adb logcat | grep ElionMDM
```

**Test Case:** Check-in Success
```
[ ] Log mostra "Check-in started"
[ ] Log mostra "Submitted payload"
[ ] Log mostra "Check-in successful"
[ ] Backend recebe telemetry
[ ] Timestamp sincronizado
```

**Test Case:** Check-in Retry
```
[ ] Desligar WiFi
[ ] Forçar check-in
[ ] Confirmar "Unable to connect - will retry"
[ ] Ligar WiFi
[ ] Confirmar auto-retry dentro de 2 min
```

**3. Remote Command Execution**

**Test Case: Reboot**
```bash
# Backend: Execute reboot comando
curl -X POST http://localhost:8000/api/commands \
  -H "Authorization: Bearer TOKEN" \
  -d '{"device_id":"uuid","type":"reboot_device"}'

# Monitorar device
[ ] Device desliga
[ ] Device liga
[ ] Check-in resume após reboot
```

**Test Case: Lock Device**
```
[ ] Backend envia comando lock_device
[ ] Device recebe comando
[ ] Home button não funciona
[ ] Power button não funciona (se policy ativa)
```

**Test Case: Disable Camera**
```
[ ] Backend envia comando disable_camera
[ ] Abrir Google Camera app
[ ] Camera não funciona (erro ao acessar)
[ ] Verification: adb shell dumpsys devicepolicy | grep camera
```

---

### Location Testing

**Emulator:**
```bash
adb emu geo fix 40.7128 -74.0060  # NYC coordinates
# Aguardar 10 segundos
adb logcat | grep "Location acquired"
# Verificar latitude/longitude nos logs
```

**Real Device:**
```
[ ] GPS On em Settings
[ ] Grant background location permission
[ ] Outdoor (better GPS signal)
[ ] Aguardar 30 segundos para fix
[ ] Verificar location em check-in telemetry
```

---

### Battery & Performance

**Test Battery Consumption:**
```bash
# Clear stats
adb shell dumpsys batterystats --reset

# Use app for 1 hour in background
# Then check
adb shell dumpsys batterystats | grep "Approximate battery remaining"

# Expected: < 10% drain com check-in a cada 15 min
```

**Test Memory Usage:**
```bash
# Monitorar via Android Profiler
# AndroidStudio → Profiler → Memory

# Expected:
# - Initial: 150-200 MB
# - After 1h: 200-300 MB (não crescendo indefinidamente)
# - Nenhum GC lag > 100ms
```

---

## 🖥️ Frontend Tests (React)

### Unit & Integration Tests

Run:
```bash
cd frontend/
npm test  # Vitest runner
```

**Test Files:**
- `src/test/example.test.ts` - Example test
- Add more tests in `src/pages/__tests__/`

---

### Manual Testing - Web Dashboard

#### Prerequisites
- React dev server: `npm run dev`
- Backend running: `python main.py`
- Logged in as admin

#### Test Scenarios

**1. Dashboard Page**
```
[ ] Devices count accurate
[ ] Active policies count correct
[ ] Status indicators update
[ ] Charts load without errors
[ ] No console errors
```

**2. Device Management**
```
[ ] List shows all devices
[ ] Device search works
[ ] Sort by status/name/enrollment works
[ ] Click device → detail page
[ ] Detail shows telemetry
[ ] Commands section visible
```

**3. Command Execution via UI**
```
[ ] Reboot button → API call
[ ] Command queued confirmation
[ ] Device receives and executes
[ ] Status updates in real-time
```

**4. Policy Management**
```
[ ] List all policies
[ ] Create new policy form works
[ ] Policy assignment to device
[ ] Policy enforcement verified
```

**5. Logs Page**
```
[ ] All logs visible
[ ] Filtering by type works
[ ] Filtering by severity works
[ ] Search functionality works
[ ] Date range filter works
[ ] CSV export generates file
[ ] Log details expand/collapse
```

**6. Settings Page**
```
[ ] System health section visible
[ ] Admin management form functional
[ ] Can add new admin
[ ] Notification toggles work
[ ] Backup/restore buttons present
[ ] System info displays correctly
```

---

### Cross-browser Testing

| Browser | OS | Status |
|---------|----|----|
| Chrome 120+ | Windows | ✅ Primary |
| Firefox 115+ | Windows | ✅ Secondary |
| Safari 16+ | macOS | ⏳ Test |
| Edge 120+ | Windows | ✅ Supported |
| Mobile Chrome | Android | ✅ Supported |

---

## 🔒 Security Tests

### Authentication Tests

```
[ ] No credentials in localStorage (only HTTP-only cookie)
[ ] CORS headers correct
[ ] XSS protection: inputs sanitized
[ ] CSRF token present on forms
[ ] Session timeout after 30 min inactivity
[ ] Force password change on first login
```

### API Security Tests

```
[ ] All endpoints require authentication
[ ] Device ID verified before returning data
[ ] Command execution only for authorized devices
[ ] Audit logs recorded for sensitive operations
[ ] Rate limiting active (10 req/sec per device)
```

### Network Security Tests

```bash
# Verificar HTTPS
curl -I https://api.example.com
# Esperado: 200 OK com HTTPS

# Verificar certificate pinning
adb logcat | grep "Certificate pinned"
```

---

## 📊 Integration Tests (End-to-End)

### Scenario 1: Full Device Enrollment → Policy Application

```
Step 1: Device Provisioning
├─ [ ] APK installed via ADB
├─ [ ] Set as Device Owner
└─ [ ] Permissions granted

Step 2: Initial Check-in
├─ [ ] Device acquires location
├─ [ ] Sends telemetry
└─ [ ] Backend creates device record

Step 3: Policy Assignment
├─ [ ] Admin assigns policy via dashboard
├─ [ ] Device receives policy on next check-in
└─ [ ] Device applies policy successfully

Step 4: Verification
├─ [ ] Dashboard shows device as compliant
├─ [ ] Logs recorded all steps
└─ [ ] No errors in production
```

### Scenario 2: Remote Command → Execution → Status Update

```
Step 1: Command Queue
├─ [ ] Admin clicks "Reboot Device"
└─ [ ] Backend queues command

Step 2: Device Receives
├─ [ ] Next check-in retrieves command
└─ [ ] Logcat shows "Executing reboot"

Step 3: Execution
├─ [ ] Device reboots
└─ [ ] Uptime counter resets

Step 4: Status Update
├─ [ ] Device check-in after reboot
├─ [ ] Backend records "executed"
└─ [ ] Dashboard shows success
```

---

## 🎯 Pre-Release Checklist

### 1 Week Before Release

- [ ] All tests passing (unit, integration, E2E)
- [ ] Code review completed
- [ ] Security scan passed
- [ ] Performance benchmarks acceptable
- [ ] Documentation updated
- [ ] Release notes written

### 3 Days Before Release

- [ ] Final security audit
- [ ] Staging deployment successful
- [ ] Load test (1000 devices) passed
- [ ] Migration tested (if DB schema changed)
- [ ] Rollback procedure documented

### Day Before Release

- [ ] APK signed with production key
- [ ] Backend docker image built and tested
- [ ] Frontend production build tested
- [ ] Monitoring alerts configured
- [ ] Team on-call schedule confirmed

### Release Day

- [ ] Deploy backend first
- [ ] Wait 5 min, verify healthy
- [ ] Deploy frontend
- [ ] Wait 5 min, verify no 5xx errors
- [ ] Push Android APK to Play Store (staged rollout 10%)
- [ ] Monitor for 1 hour

### Post-Release (48h)

- [ ] No critical errors reported
- [ ] Device check-ins flowing smoothly
- [ ] Commands executing normally
- [ ] Performance metrics healthy
- [ ] Increase Android rollout to 100%

---

## 📈 Test Metrics

### Target Coverage

```
Backend:
├─ Unit test coverage: >80%
├─ Integration test coverage: >70%
├─ API endpoint coverage: 100%
└─ Critical path coverage: 95%

Android:
├─ Unit test coverage: >70%
├─ Instrumentation test coverage: >60%
├─ Scenarios tested: 100%
└─ Device types tested: ≥3

Frontend:
├─ Component coverage: >60%
├─ Page coverage: 100%
├─ Critical flows: 95%
└─ Browsers tested: ≥3
```

### Quality Gates

| Metric | Threshold | Action |
|--------|-----------|--------|
| Test Pass Rate | >99% | Fail if <99% |
| Code Coverage | >75% | Warn if <75% |
| Critical Bugs | 0 | Block release |
| High Bugs | <5 | Review required |
| API Response Time | <200ms | Optimize |
| Device Check-in Rate | >98% | Investigate |

---

## 🔄 Regression Testing

After Each Release, Verify:

```
[ ] Previous functionality still works
[ ] No new crashes reported
[ ] Database migrations completed
[ ] API responses same format
[ ] Performance not degraded
[ ] Security measures intact
```

---

## 📞 Test Execution

### Running All Tests

```bash
# Backend
cd backend/
pytest tests/ -v --cov=api --cov-report=html

# Android
cd android/
./gradlew test connectedAndroidTest

# Frontend
cd frontend/
npm test -- --coverage
```

### CI/CD Pipeline

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Backend Tests
        run: cd backend && pytest tests/
      - name: Frontend Tests
        run: cd frontend && npm test
      - name: Build Android
        run: cd android && ./gradlew assemble
```

---

**Test Plan Version:** 1.0.0  
**Last Updated:** Março 5, 2026  
**Owner:** QA Team  
**Frequency:** Updated per sprint
