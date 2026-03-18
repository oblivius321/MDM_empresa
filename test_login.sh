#!/bin/sh
curl -X POST http://localhost:3000/api/auth/login \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  --data '{"email":"admin@empresa.com","password":"AdminSenhaForte123!"}' \
  -i
