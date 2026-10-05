# Digital Product Store — FastAPI + React Vite + Stripe

## Features
- JWT registration/login/profile
- Admin product CRUD
- Product search + pagination
- User cart management
- Orders + pagination
- Stripe Checkout + webhook status updates
- Admin statistics and 3 SQL reports
- React Vite pages and React Toastify notifications
- Pytest tests

## 1. Backend
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```
Swagger: http://127.0.0.1:8000/docs

The first registered user becomes ADMIN for easy testing.

## 2. Frontend
Install Node.js, then:
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```
Open the Vite URL, normally http://localhost:5173.

## 3. Stripe
Put your Stripe test secret in `backend/.env`:
`STRIPE_SECRET_KEY=sk_test_...`

For a real webhook:
`STRIPE_WEBHOOK_SECRET=whsec_...`

Stripe CLI example:
```powershell
stripe listen --forward-to localhost:8000/payments/webhook
```
Copy the webhook secret into `.env`.

Use Stripe test cards in test mode, e.g. 4242 4242 4242 4242, any future expiry, any CVC.

If Stripe keys are empty, checkout returns the Orders page as a demo fallback so the rest of the assignment can still be demonstrated.

## 4. Tests
```powershell
cd backend
pytest -q
```

## API
Auth:
POST /auth/register
POST /auth/login
GET /auth/profile

Products:
POST /products
GET /products?page=1&limit=10&search=python
GET /products/{id}
PUT /products/{id}
DELETE /products/{id}

Cart:
GET /cart
POST /cart/items
PUT /cart/items/{item_id}
DELETE /cart/items/{item_id}
DELETE /cart

Payments:
POST /payments/create-checkout-session
POST /payments/webhook

Orders:
GET /orders?page=1&limit=5
GET /orders/{id}

Admin:
GET /admin/stats
GET /admin/orders
GET /admin/reports

## Submission evidence
Capture:
1. Swagger `/docs`
2. React products page
3. Cart page
4. Stripe Checkout test page
5. Orders showing PAID after webhook
6. Admin statistics
7. `pytest -q` output
