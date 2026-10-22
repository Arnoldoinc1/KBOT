# Account and database compatibility

## Why an old account can appear to disappear

Teacher and Student accounts are rows in the shared `users` table. Docker Compose names unnamed volumes from the folder/project name. The earlier v8.0.2 Compose file therefore created a new project-specific MySQL volume instead of opening the original v6.2 volume. Registration could succeed in that new database while accounts such as `test1` remained in the old volume.

v8.0.5 explicitly uses this v6.2 volume by default:

```dotenv
MYSQL_VOLUME_NAME=edu_qa_mysql_data
```

The migration adds new columns in place. It does not replace usernames, roles, password hashes, or old answer records.

## Check which accounts the applications can see

On Windows, run:

```text
CHECK_ACCOUNTS.bat
```

It connects through the root `.env` `DATABASE_URL` and prints only account IDs, usernames, display names, and roles. It never prints password hashes.

If `test1` is listed as `student`, the Student App is using the correct database. If it is absent, the application is connected to another database/volume; changing the web login page cannot recover an account that is not present in that database.

## Local Python services with MySQL in Docker

If the original `edu_qa_mysql` container is already running on port 3307, keep it running and set:

```dotenv
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@127.0.0.1:3307/edu_qa?charset=utf8mb4
```

Then run `CHECK_ACCOUNTS.bat`, followed by `START_ALL.bat`. Do not start a second MySQL container on the same port.

If v8.0.2 Compose is running instead, stop it without deleting volumes:

```bat
docker compose down
```

Then, from the v8.0.5 root:

```bat
docker compose up -d mysql
```

Never run `docker compose down -v` while preserving accounts and history.

## Teacher access

The original teacher interface and registration route are restored. Visit `/register` or use the **Create one** link on the login page.

For local backward compatibility, when no teacher/admin account exists, the Teacher App creates the original local fallback account:

```text
teacher1 / 123456
```

Set `LEGACY_TEACHER_COMPAT=false` and `SEED_DEMO_TEACHER=false` to disable that behavior in deployment. Change the demo password before exposing the service beyond a trusted local machine.

## Cookie isolation

Teacher and Student use separate cookie names:

```text
kbot_teacher_session
kbot_student_session
```

Logging into one portal no longer overwrites the other portal session merely because both use `127.0.0.1` on different ports.
