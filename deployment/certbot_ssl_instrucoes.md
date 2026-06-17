# Instrucoes para SSL com Certbot

1. Aponte o DNS `api.saberes.cloud` para o IP da VPS.
2. Ative a configuracao do nginx.
3. Instale o Certbot na VPS.
4. Execute o Certbot para `api.saberes.cloud`.
5. Aceite a redirecao de HTTP para HTTPS.
6. Teste o acesso em `https://api.saberes.cloud/health`.

Comando de referencia:

```bash
sudo certbot --nginx -d api.saberes.cloud
```
