# Empório da Música — agente de atendimento

Protótipo em Python para o desafio técnico de AI Engineer da Artefact.
O objetivo é auxiliar o atendimento de uma loja fictícia de instrumentos
musicais, respondendo com base nos dados da operação e nas políticas fornecidas.



## Escopo

- Conversar com tom acolhedor, informal e profissional.
- Consultar o catálogo para informar preços, disponibilidade e promoções.
- Consultar pedidos, definindo antes como identificar o cliente e restringir o acesso.
- Consultar o manual para responder sobre horários, pagamentos, entregas e trocas.
- Reconhecer perguntas fora do escopo e informar quando faltar informação.
- Usar um modelo de linguagem integrado às consultas, sem inventar dados da loja.

## Materiais de referência

O material recebido contém seis tabelas CSV: `categories`, `customers`,
`order_items`, `orders`, `products` e `promotions`, além do PDF de políticas
da loja.



## Decisões iniciais

### Interface pelo terminal

A primeira interface será uma CLI (interação por texto no terminal). Ela permite
demonstrar o fluxo de conversa e as consultas com pouca infraestrutura.
Uma interface web exigiria trabalho adicional de apresentação e comunicação
entre componentes sem ser necessária para demonstrar o agente neste desafio.

### Implementação incremental

Cada etapa terá uma entrega pequena, validada e registrada em um commit.
Começaremos pelas consultas aos dados antes da integração com o modelo, para
conseguir verificar os resultados dessas consultas de forma independente.
Isso também ajuda a distinguir falhas nos dados de falhas na resposta do modelo.

### Configuração e segredos fora do Git

Chaves de API e configurações locais não serão versionadas. Quando houver uma
integração que exija configuração, adicionaremos um `.env.example` sem segredos.
O `.gitignore` inicial também exclui ambientes virtuais e arquivos temporários.



## Plano de implementação

1. Documentar o escopo e preparar o versionamento.
2. Incorporar, ler e validar os dados fornecidos.
3. Implementar consultas de produtos, estoque e promoções.
4. Implementar a consulta das políticas da loja.
5. Integrar o modelo e disponibilizar a conversa no terminal, incluindo consultas
   de pedidos com as restrições de acesso definidas.
6. Validar os cenários, registrar de três a cinco conversas reais com o agente
   e concluir as instruções de execução e limitações.

## Validação planejada

Os testes serão adicionados junto com as regras implementadas. Os cenários
prioritários incluem filtros de produtos, indisponibilidade, promoções inativas,
regras de desconto, informações ausentes, consulta de pedidos e perguntas fora
do escopo. A integração com o modelo também precisará de validação com conversas
reais.

## Limitações atuais

- Os dados fornecidos são uma fotografia da operação; não existe integração com
  um sistema de produção ou com WhatsApp.
- As políticas podem conter ambiguidades. As interpretações adotadas serão
  documentadas conforme forem identificadas e implementadas.

## Uso de assistência de IA

Este projeto está sendo desenvolvido com auxílio de uma ferramenta para codificação chamada Cursor, pela familiaridade que possuo com a mesma tendo em vista já ter utilizado, inclusive no plano pago, para completar código e sugestão de codificação. Isso me ajudou muito em termos de produtividade.

Este registro será atualizado conforme o desenvolvimento avançar.
