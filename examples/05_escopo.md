# Perguntas fora do escopo e acessórios

Registro automático de uma conversa real com a aplicação. As respostas abaixo não foram editadas.

Objetivo do cenário: Observar a orientação de escopo e o atendimento a uma solicitação de acessórios.

- Início: 2026-11-03T15:37:14-03:00
- Modelo solicitado: `qwen3:4b-instruct`
- Python: 3.9.6
- Commit da aplicação: `24cf425`
- Cliente da sessão simulada: nenhum

O objetivo do cenário não representa uma aprovação do resultado. As respostas incluem as proteções e referências acrescentadas pela aplicação. As ferramentas podem ser acionadas pelo modelo ou pela recuperação determinística da aplicação. Tempos são observações desta execução, sem caracterizar um benchmark.

## Mensagem 1

**Cliente:** Qual é a capital da França?

Ferramentas acionadas: nenhuma. Tempo observado: 0.37 s.

**Assistente:**

Meu atendimento é voltado à Empório da Música. Posso ajudar com instrumentos musicais, preços, estoque, pedidos e políticas da loja. Qual dessas informações você precisa?

## Mensagem 2

**Cliente:** Vocês vendem cabos para guitarra?

Ferramentas acionadas: `get_policy_section`. Tempo observado: 6.20 s.

**Assistente:**

Não, nós não vendemos cabos para guitarra. A Empório da Música vende apenas instrumentos musicais e não comercializa acessórios como cabos, palhetas, cordas, cases, pedais ou amplificadores.

Fontes consultadas: manual, seção 1, página 2.
