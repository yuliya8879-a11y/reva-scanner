#!/bin/sh
# Запускаем миграции. Если таблицы уже существуют — делаем stamp и повторяем.
python -m alembic upgrade head
if [ $? -ne 0 ]; then
    echo "Migration failed — stamping current state and retrying..."
    python -m alembic stamp head
    python -m alembic upgrade head
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
