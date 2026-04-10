from datetime import datetime


def insert_funding_logs(
    rows,
    host,
    port,
    user,
    password,
    database,
    table_name="funding_logs",
    connect_timeout=5,
):
    """Insert forecast-passed rows into MySQL funding_logs table."""
    if not rows:
        return 0

    try:
        import pymysql
    except Exception as e:
        print(f"⚠️ MySQL logger unavailable (PyMySQL missing): {e}")
        return 0

    sql = (
        f"INSERT INTO `{table_name}` "
        "(`timestamp`, `symbol`, `current`, `next`, `delta`, `r2`) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )

    values = []
    now = datetime.now()
    for row in rows:
        values.append(
            (
                now,
                row.get("symbol"),
                row.get("current"),
                row.get("next"),
                row.get("delta"),
                row.get("r2"),
            )
        )

    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=connect_timeout,
        )
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)
        connection.commit()
        return len(values)
    except Exception as e:
        print(f"⚠️ MySQL insert failed: {e}")
        try:
            if connection:
                connection.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            if connection:
                connection.close()
        except Exception:
            pass
