# WP3 -- Mendix Mock

Simulates the Mendix application layer. Manages the operator workflow (order state machine), integrates with WP4 (SAP mock) for orders and materials, triggers WP1 cycle start, fires MES events to WP5, and serves a Jinja2 operator UI.

## Run

```powershell
cd wp3-mendix-mock
copy .env.example .env          # edit as needed
..\\.venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

API + UI available at `http://localhost:8002`.

Requires WP4 (SAP mock) running at `localhost:8003` for order and material data.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MENDIX_API_PORT` | `8002` | FastAPI listen port |
| `SAP_API_URL` | `http://localhost:8003` | WP4 SAP mock base URL |
| `SIMATIC_API_URL` | `http://localhost:8001` | WP2 SIMATIC mock base URL |
| `WP1_CONTROL_API_URL` | `http://localhost:8080` | WP1 control API (port 8080, not 8000) |
| `WP5_WEBHOOK_URL` | `http://localhost:8005/events` | WP5 MES event webhook |
| `PLANT_ID` | `regensburg` | Plant identifier |
| `OVEN_ID` | `oven-01` | Oven identifier |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Tests

```powershell
cd wp3-mendix-mock
..\\.venv\Scripts\pytest.exe tests/ -v -m "not integration"
# with live WP4:
..\\.venv\Scripts\pytest.exe tests/ -v
```

## Sample output

`GET /orders/ORD-2026-00001/state`
```json
{
  "order_id": "ORD-2026-00001",
  "status": "in-progress",
  "operator_id": "OP-007",
  "cycle_confirmed_at": null,
  "quality_check_passed": null
}
```

`POST /orders/ORD-2026-00001/confirm`
```json
{
  "order_id": "ORD-2026-00001",
  "status": "closed",
  "sap_confirmation_number": "CONF-2026-00891"
}
```

## Architecture decisions

- **Operator UI**: Jinja2 HTML (chosen over Streamlit for simplicity and zero extra dependencies).
- **Cycle start**: WP3 calls WP1 control API (`POST /control/start`) when operator starts a cycle. WP1/WP5 failures are non-fatal (logged as warnings).
- **WP2 push vs poll**: WP5 polls WP2's historian (C3) directly; WP2 does not push webhooks to WP5.
