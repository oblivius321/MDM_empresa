import asyncio
from backend.core.security import verify_password

password_plain = 'AdminSenhaForte123!'
hash_from_db = '$2b$12$rMTvzY7H3oDGgqcyi5ZaJux.nN8faIYNforTgsCKUxVbShLqA2b7.'

result = verify_password(password_plain, hash_from_db)
print(f'Senha correta? {result}')
