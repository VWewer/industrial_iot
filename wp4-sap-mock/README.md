# WP4 -- SAP Mock

Simulates SAP S/4HANA's OData interface for the Industrial IoT demo. System of record for production orders, material master data, and goods movements.

## Contracts implemented

| Contract | Endpoint | Description |
|---|---|---|
| C6 | `GET /odata/v1/ProductionOrders` / `GET /odata/v1/ProductionOrders('{id}')` | Production order data |
| C7 | `GET /odata/v1/Materials('{id}')` | Material master |
| C8 | `POST /odata/v1/GoodsMovements` | Goods receipt posting |
| C5 | `POST /odata/v1/OperationConfirmations` | Operation confirmation from Mendix |
| C11 | All GET endpoints above | Batch pull source for WP5 |

## Quick start

```bash
cd wp4-sap-mock
cp .env.example .env
pip install -r requirements.txt
python -m src.main
# Service running on http://localhost:8003
```

Or via docker-compose (from project root):
```bash
docker-compose up wp4
```

## Running tests

```bash
cd wp4-sap-mock
..\.venv\Scripts\pytest.exe tests/ -v
```

## Required environment variables

| Variable | Default | Description |
|---|---|---|
| `SAP_API_PORT` | `8003` | Port the service listens on |
| `PLANT_ID` | `regensburg` | Plant identifier |

## API docs

OpenAPI docs available at `http://localhost:8003/docs` when running.

---

## Sample output

All timestamps are ISO 8601 UTC with `Z` suffix. Phase 4 validated 2026-06-03.

### GET /health
```json
{
  "status": "ok",
  "service": "wp4-sap-mock",
  "orders": 4,
  "materials": 4
}
```

### GET /odata/v1/ProductionOrders('ORD-2026-00042')
```json
{
  "order_id": "ORD-2026-00042",
  "material_id": "MAT-0001",
  "plant": "regensburg",
  "oven_id": "oven-01",
  "planned_start": "2026-06-03T06:00:00Z",
  "planned_end": "2026-06-03T14:00:00Z",
  "standard_cycle_minutes": 480,
  "status": "RELEASED",
  "operator_id": null,
  "actual_start": null,
  "actual_end": null,
  "sap_confirmation_number": null,
  "goods_movement_posted": false,
  "created_at": "2026-06-02T14:30:00Z",
  "updated_at": "2026-06-02T14:30:00Z"
}
```

### GET /odata/v1/Materials('MAT-0001')
```json
{
  "material_id": "MAT-0001",
  "material_description": "Power Transformer 100MVA",
  "insulation_class": "H",
  "target_moisture_ppm": 300,
  "standard_cycle_minutes": 480,
  "max_cycle_minutes": 600,
  "target_temperature_degC": 130.0,
  "target_vacuum_mbar": 5.0,
  "weight_kg": 8500.0,
  "updated_at": "2026-06-01T00:00:00Z"
}
```

### POST /odata/v1/OperationConfirmations (C5)

Request:
```json
{
  "order_id": "ORD-2026-00042",
  "operation_id": "ORD-2026-00042-OPR-010",
  "confirmed_quantity": 1.0,
  "actual_start": "2026-06-03T06:05:00Z",
  "actual_end": "2026-06-03T13:58:00Z",
  "operator_id": "OP-007",
  "final_moisture_ppm": 287.4,
  "spec_met": true
}
```

Response:
```json
{
  "order_id": "ORD-2026-00042",
  "sap_confirmation_number": "CONF-2026-00901",
  "status": "CONFIRMED",
  "posted_at": "2026-06-03T14:00:03Z"
}
```

### POST /odata/v1/GoodsMovements (C8)

Request:
```json
{
  "order_id": "ORD-2026-00042",
  "material_id": "MAT-0001",
  "movement_type": "GR_PRODUCTION",
  "quantity": 1,
  "unit": "EA",
  "posting_date": "2026-06-03",
  "storage_location": "WH-01"
}
```

Response:
```json
{
  "document_number": "GR-2026-003901",
  "order_id": "ORD-2026-00042",
  "material_id": "MAT-0001",
  "movement_type": "GR_PRODUCTION",
  "quantity": 1.0,
  "unit": "EA",
  "posting_date": "2026-06-03",
  "storage_location": "WH-01",
  "posted_at": "2026-06-03T14:00:05Z",
  "status": "posted"
}
```

---

## Phase 4 seam validation

**Date:** 2026-06-03
**Method:** `contracts/validators/run_wp4_phase4_check.py` (in-process TestClient)
**Result: 18/18 PASS**

| Contract | Checks | Result |
|---|---|---|
| C6 ProductionOrders (4 single + 4 list) | 8 | PASS |
| C7 Materials (4 single + 4 list) | 8 | PASS |
| C5 OperationConfirmations (response) | 1 | PASS |
| C8 GoodsMovements (response) | 1 | PASS |

Validators: `contracts/validators/validate_c5_confirmation_response.py`,
`validate_c6_production_order.py`, `validate_c7_material_master.py`,
`validate_c8_goods_movement.py`

---

## Seed data

| order_id | material_id | status | notes |
|---|---|---|---|
| ORD-2026-00042 | MAT-0001 | RELEASED | Active demo order |
| ORD-2026-00041 | MAT-0002 | CONFIRMED | Most recent historical |
| ORD-2026-00039 | MAT-0003 | ABORTED | Deviation case |
| ORD-2026-00043 | MAT-0004 | CREATED | Queued, not yet released |

## State machine

```
CREATED -> RELEASED -> IN_PROGRESS -> CONFIRMED -> CLOSED
   |           |             |
   v           v             v
ABORTED    ABORTED       ABORTED
```
