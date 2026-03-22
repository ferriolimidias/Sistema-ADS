from fastapi import APIRouter

router = APIRouter(tags=["platform-sync"])


@router.get("/google-accounts")
def get_google_accounts():
    return [
        {"nome": "Cliente A", "id": "12345"},
        {"nome": "Cliente B", "id": "67890"},
    ]


@router.get("/meta-accounts")
def get_meta_accounts():
    return [
        {"nome": "Cliente A", "id": "act_12345"},
        {"nome": "Cliente B", "id": "act_67890"},
    ]
