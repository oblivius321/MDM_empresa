# Guia de Instalação do Agente MDM via ADB

Este guia descreve os passos necessários para instalar manualmente o agente Android no dispositivo (ou emulador) e configurá-lo como **Device Owner** utilizando as ferramentas do Android Debug Bridge (ADB).

---

## 1. Pré-requisitos

Antes de começar, certifique-se de que:
*   O **ADB** está instalado no seu computador e configurado no PATH do sistema.
*   A **Depuração USB** está ativada no dispositivo (ou o emulador está rodando).
*   **Importante**: Não deve haver nenhuma conta (Google, Samsung, etc.) configurada no dispositivo. Caso existam, o Android impedirá a definição do Device Owner por segurança. Remova-as em *Configurações > Contas*.

---

## 2. Localização do Arquivo APK

O APK atualizado para desenvolvimento está localizado no diretório estático do backend:
`backend/static/elion-mdm.apk`

---

## 3. Procedimento de Instalação

### Passo 1: Verificar a conexão do dispositivo
Abra o terminal e verifique se o seu dispositivo ou emulador é listado:
```bash
adb devices (não esqueça de entrar no celular e ir em configurações e ativar a depuração usb no modo desenvolvedor)
```

### Passo 2: Instalar o aplicativo

Na raiz do projeto, execute o comando de instalação:
cd "caminho do projeto"

```bash "adb install -t + o nome do apk"

adb install backend/static/elion-mdm.apk (não esqueça de entrar na pasta do projeto no terminal)
```

### Passo 3: Definir como Proprietário do Dispositivo (Device Owner)
Para que o MDM tenha controle total sobre as políticas de segurança e modo Kiosk, você deve executar o seguinte comando:

```bash
adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver
```

---

## 4. Solução de Problemas Comuns

| Problema | Causa Provável | Solução |
| :--- | :--- | :--- |
| `Not allowed to set the device owner because there are already some accounts` | Existem contas ativas no sistema. | Remova todas as contas (Gmail, WhatsApp, etc.) nas configurações do Android. |
| `Component info is invalid` | Erro de digitação no nome do Receiver. | Certifique-se de usar exatamente `com.elion.mdm/.AdminReceiver`. |
| `Device not found` | Dispositivo desconectado ou driver faltando. | Verifique o cabo e se o comando `adb devices` retorna um ID. |

---

## 5. Próximos Passos
Após concluir a instalação, abra o aplicativo **Elion MDM**. Ele iniciará automaticamente o processo de provisionamento e conexão com o servidor local rodando na porta 8000. (se não puxar automaticamente é só você colocar o ip do seu backend, e o bootstrap secret (cuidado e não espalhe suas chaves de forma publica, elas são sensiveis ) logo após isso deverá iniciar o app normalmente)



                             ░██                                
                             ░██                                
░██    ░██    ░██  ░██████   ░██ ░██░████ ░██    ░██  ░███████  
░██    ░██    ░██       ░██  ░██ ░███     ░██    ░██ ░██        
 ░██  ░████  ░██   ░███████  ░██ ░██      ░██    ░██  ░███████  
  ░██░██ ░██░██   ░██   ░██  ░██ ░██      ░██   ░███        ░██ 
   ░███   ░███     ░█████░██ ░██ ░██       ░█████░██  ░███████  
                                                                                                                        