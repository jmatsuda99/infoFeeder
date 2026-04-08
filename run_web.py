if __name__ == "__main__":
    import uvicorn

    # reload=True: .py 変更時にサーバーが再起動する（ブラウザを更新すると最新コードが効く）
    uvicorn.run(
        "webapp.main:app",
        host="127.0.0.1",
        port=8510,
        reload=True,
    )
