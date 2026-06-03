# Como publicar uma release

Versionamento [Semântico](https://semver.org/lang/pt-BR/):

| Tipo | Quando | Exemplo |
|------|--------|---------|
| **MAJOR** | Quebra de contrato / arquitetura | `2.0.0` |
| **MINOR** | Feature nova compatível | `1.1.0` (F10) |
| **PATCH** | Correção, docs, ajuste fino | `1.1.1` |

## Checklist

1. Atualizar `CHANGELOG.md` (seção da nova versão + data).
2. Atualizar `VERSION` na raiz.
3. `python -m pytest`
4. Commit: `chore(release): preparar vX.Y.Z`
5. Tag anotada no commit da feature (ou no commit de release):

   ```powershell
   git tag -a vX.Y.Z <commit-sha> -m "vX.Y.Z — resumo curto"
   git push origin vX.Y.Z
   ```

6. Criar **GitHub Release** a partir da tag (corpo = notas do CHANGELOG).

```powershell
# Exemplo (requer GitHub CLI: gh)
gh release create vX.Y.Z --title "vX.Y.Z — título" --notes-file CHANGELOG-excerpt.md
```

## Tags deste repositório

| Tag | Commit | Conteúdo |
|-----|--------|----------|
| `v1.0.0` | `f67a25d` | Release inicial pública |
| `v1.1.0` | `5ece5be` | F10 — thinking policy |
