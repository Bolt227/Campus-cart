# Campus Cart

A student-to-student marketplace for VIT. Built with Flask, SQLite and plain JavaScript, with Cashfree for payments.

## Run locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit .env (SECRET_KEY is required)
cd backend
python app.py
```

Open http://127.0.0.1:5000

## Payments (Cashfree)

1. Put your **sandbox** `CASHFREE_APP_ID` and `CASHFREE_SECRET_KEY` in `.env`.
2. Keep `CASHFREE_MODE=sandbox` until a full test payment works.
3. When an item is bought, it is reserved (`pending`) for 30 minutes, and marked `sold` only after
   the server confirms the payment with Cashfree. Expired or cancelled payments release the item.
4. In the Cashfree dashboard set the webhook URL to `https://YOUR-SITE/api/payments/webhook`.
   Set `PUBLIC_BASE_URL` to your site address (https) so return and webhook URLs are correct.

## Deploy

**PythonAnywhere:** in the WSGI file add `/home/YOU/Campus-cart/backend` to `sys.path`, then
`from app import app as application`. Put your variables in a `.env` file inside `backend/`.

**Render:** Build `pip install -r requirements.txt`, Start `gunicorn --chdir backend app:app`.
Add the variables from `.env.example` in the Environment tab. Set `DATA_DIR` to a persistent disk
path, otherwise the database and uploads are lost on every deploy.

## Project layout

```
backend/app.py      Flask app, API and Cashfree payment logic
frontend/templates  HTML pages
frontend/static     CSS and JavaScript
```
