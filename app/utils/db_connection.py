import cx_Oracle
# Oracle 클라이언트 라이브러리 경로 설정
cx_Oracle.init_oracle_client(lib_dir=r"C:\oracle\instantclient\instantclient-basic-windows.x64-23.6.0.24.10\instantclient_23_6")



# Oracle DB 연결 함수
def get_oracle_connection():
    try:
        # Oracle DB 연결 설정 (환경에 맞게 수정)
        dsn = cx_Oracle.makedsn("ktj0514.synology.me", "1521", service_name="xe")
        connection = cx_Oracle.connect(user="C##SS", password="1234", dsn=dsn)
        return connection
    except cx_Oracle.DatabaseError as e:
        print(f"Database connection error: {e}")
        return None


# USER_FACEID_STATUS 업데이트 함수
def update_faceid_status(uuid: str):
    connection = get_oracle_connection()
    if connection:
        try:
            with connection.cursor() as cursor:
                # UPDATE 쿼리 준비
                update_query = """
                    UPDATE USERS
                    SET USER_FACEID_STATUS = 'Y'
                    WHERE uuid = :uuid
                """
                # 쿼리 실행
                cursor.execute(update_query, {'uuid': uuid})

                # 변경 사항 커밋
                connection.commit()

                print(f"USER_FACEID_STATUS가 Y로 업데이트되었습니다. UUID: {uuid}")

        except cx_Oracle.DatabaseError as e:
            print(f"Error executing update query: {e}")

        finally:
            # 연결 종료
            connection.close()
    else:
        print("DB 연결 실패")
