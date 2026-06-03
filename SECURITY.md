# Política de segurança

## Reportar vulnerabilidades

Se você encontrar um problema de segurança, **não** abra uma issue pública no GitHub com detalhes de exploração. Use um security advisory privado no repositório ou contate os mantenedores diretamente.

## Segredos e configuração local

Nunca commite:

- `.env` ou qualquer arquivo com API keys, JWT secrets ou senhas de banco reais
- `scripts/llama-paths.local.bat` (caminhos específicos da máquina)
- Volumes Docker, pesos de modelo (`.gguf`) ou exportações de dados de usuário

Use `.env.example` como modelo e gere valores únicos em cada instalação.

## Antes do primeiro push

1. Confirme que `.env` está ignorado: `git check-ignore -v .env`
2. Varra o staging: `git grep -i "api_key\|secret\|password" --cached` (deve aparecer só placeholders e exemplos)
3. Se um segredo já foi commitado, rotacione e reescreva o histórico (`git filter-repo` ou BFG) antes de publicar

## Notas operacionais

- `LITELLM_MASTER_KEY` protege o proxy LiteLLM; o LibreChat usa o mesmo valor no endpoint customizado.
- `X-User-Id` é fail-closed (`jean` | `tati` por padrão); não enfraqueça allowlists em produção.
- Chaves de API do AnythingLLM são criadas na UI do AnythingLLM; armazene apenas no `.env`.
