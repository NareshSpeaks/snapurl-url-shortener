

import validators
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from starlette.datastructures import URL

from . import crud, models, schemas
from .database import SessionLocal, engine
from .config import get_settings

app = FastAPI(
    title="Naresh URL Shortener 🚀",
    description="A simple and powerful URL shortener built with FastAPI",
    version="1.0.0"
)

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_admin_info(db_url: models.URL) -> schemas.URLInfo:
    base_url = URL(get_settings().base_url)
    admin_endpoint = app.url_path_for(
        "administration info", secret_key=db_url.secret_key
    )
    db_url.url = str(base_url.replace(path=db_url.key))
    db_url.admin_url = str(base_url.replace(path=admin_endpoint))
    return db_url


def raise_bad_request(message):
    raise HTTPException(status_code=400, detail=message)


def raise_not_found(request):
    message = f"URL '{request.url}' doesn't exist"
    raise HTTPException(status_code=404, detail=message)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>SnapURL</title>
        <style>
            body {
                font-family: Arial;
                text-align: center;
                margin-top: 100px;
                background: #0f172a;
                color: white;
            }
            input {
                padding: 12px;
                width: 350px;
                border-radius: 8px;
                border: none;
            }
            button {
                padding: 12px 20px;
                margin-left: 10px;
                background: #22c55e;
                border: none;
                border-radius: 8px;
                cursor: pointer;
            }
            .card {
                margin-top: 20px;
                background: #1e293b;
                padding: 20px;
                border-radius: 10px;
                display: inline-block;
            }
            .error {
                color: red;
                margin-top: 20px;
            }
        </style>
    </head>

    <body>
        <h1> SnapURL </h1>
        <h2>Shorten your URL in just one click!</h2>

        <input id="url" placeholder="Enter your URL">
        <button id="btn" onclick="shorten()">Shorten</button>

        <div id="result"></div>

        <script>
            async function shorten() {
                const url = document.getElementById("url").value;
                const resultDiv = document.getElementById("result");
                const btn = document.getElementById("btn");

                //  Loading state
                btn.innerText = "Shortening...";
                btn.disabled = true;

                try {
                    const res = await fetch("/url", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({target_url: url})
                    });

                    const data = await res.json();

                    //  Error handling
                    if (!res.ok) {
                        resultDiv.innerHTML = `<p class="error"> ${data.detail}</p>`;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="card">
                                <p>Short URL:</p>
                                <a href="${data.url}" target="_blank">${data.url}</a><br><br>

                                <button onclick="copyText('${data.url}', this)">Copy</button>
                                <button onclick="window.open('${data.url}')">Open</button>
                            </div>
                        `;
                    }

                } catch (err) {
                    resultDiv.innerHTML = `<p class="error"> Something went wrong</p>`;
                }

                // Reset button
                btn.innerText = "Shorten";
                btn.disabled = false;
            }

            //  Copy animation
            function copyText(text, btn) {
                navigator.clipboard.writeText(text);
                btn.innerText = "Copied!!";

                setTimeout(() => {
                    btn.innerText = "Copy";
                }, 2000);
            }
        </script>
    </body>
    </html>
    """


@app.post("/url", response_model=schemas.URLInfo)
def create_url(url: schemas.URLBase, db: Session = Depends(get_db)):
    if not validators.url(url.target_url):
        raise_bad_request("Invalid URL")

    db_url = crud.create_db_url(db=db, url=url)
    return get_admin_info(db_url)


@app.get("/{url_key}")
def forward_to_target_url(url_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.get_db_url_by_key(db=db, url_key=url_key):
        crud.update_db_clicks(db=db, db_url=db_url)
        return RedirectResponse(db_url.target_url)
    else:
        raise_not_found(request)


@app.get("/admin/{secret_key}", name="administration info", response_model=schemas.URLInfo)
def get_url_info(secret_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.get_db_url_by_secret_key(db, secret_key=secret_key):
        db_url.url = db_url.key
        db_url.admin_url = db_url.secret_key
        return get_admin_info(db_url)
    else:
        raise_not_found(request)


@app.delete("/admin/{secret_key}")
def delete_url(secret_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.deactivate_db_url_by_secret_key(db, secret_key):
        return {"detail": "URL deleted successfully"}
    else:
        raise_not_found(request)
