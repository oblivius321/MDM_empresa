@echo off
echo Iniciando MDM System...

:: Inicia o Backend em uma nova janela
start "MDM Backend (Porta 8000)" cmd /k "title MDM Backend && .venv\Scripts\activate && python -m uvicorn backend.main:app --reload"

:: Verifica se npm existe antes de tentar iniciar o frontend
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Node.js (npm) nao encontrado!
    echo O Frontend nao pode ser iniciado.
    echo Por favor, instale o Node.js em https://nodejs.org/
    echo.
    pause
    exit /b
)

:: Inicia o Frontend em uma nova janela
cd frontend
echo Instalando dependencias do Frontend (pode demorar na primeira vez)...
call npm install
start "MDM Frontend (Porta 8080)" cmd /k "title MDM Frontend && npm run dev"

echo.
echo Tudo iniciado! 
echo Backend: http://localhost:8000/docs
echo Frontend: http://localhost:8080 (ou a porta que o Vite escolher)
echo.
pause
