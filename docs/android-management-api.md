# Android Management API

O Elion MDM usa a Android Management API para gerar QR Codes oficiais com o
DPC aprovado pelo Google, o Android Device Policy. Esse fluxo substitui o QR
legado que tentava instalar `com.elion.mdm` como DPC direto por URL própria.

## Segredo da Service Account

Nunca cole o JSON da service account em chat, issue, commit ou arquivo
versionado. O backend lê a chave local a partir de:

```text
ANDROID_MANAGEMENT_SERVICE_ACCOUNT_FILE=secrets/android-management-service-account.json
```

O diretório `secrets/` está ignorado pelo Git e montado no container backend em
modo somente leitura.

Se uma chave privada foi colada em qualquer lugar, revogue essa chave no Google
Cloud e crie uma nova:

```text
IAM & Admin -> Service Accounts -> elion-mdm-service -> Keys
```

Depois salve o novo JSON em:

```text
C:\Users\Admin\Documents\MDM_PROJETO\secrets\android-management-service-account.json
```

## Fluxo no painel

1. Abra `Provisionamento`.
2. Na seção `Android Enterprise oficial`, clique em `Conectar Enterprise`.
3. Conclua o cadastro na aba do Google.
4. Volte ao painel e clique em `Criar Policy Default`.
5. Clique em `Gerar QR Oficial`.
6. Use esse QR no celular restaurado de fábrica.

O QR oficial vem do campo `qrCode` retornado por:

```text
POST /v1/{enterprise}/enrollmentTokens
```

## Variáveis

```text
ANDROID_MANAGEMENT_PROJECT_ID=mdm-projeto2
ANDROID_MANAGEMENT_SERVICE_ACCOUNT_FILE=secrets/android-management-service-account.json
ANDROID_MANAGEMENT_KIOSK_PACKAGE=
```

`ANDROID_MANAGEMENT_KIOSK_PACKAGE` só deve ser preenchido depois que o app
estiver publicado como app privado/gerenciado no Managed Google Play.
