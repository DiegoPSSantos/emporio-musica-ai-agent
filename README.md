# Empório da Música — agente de atendimento

Protótipo em Python para o desafio técnico de AI Engineer da Artefact.
O objetivo é auxiliar o atendimento de uma loja fictícia de instrumentos
musicais, respondendo com base nos dados da operação e nas políticas fornecidas.

## Estado atual e execução

A aplicação possui leitura e validação dos dados, consultas ao catálogo,
recuperação de políticas e conversa pelo terminal com um modelo local via Ollama.

### Conversar com o agente

Instale o [Ollama](https://docs.ollama.com/macos). No macOS com Homebrew:

```bash
brew install ollama
```

Se o servidor não estiver ativo, execute `ollama serve` em um terminal e mantenha-o
aberto. Se estiver usando o aplicativo Ollama já aberto, essa etapa pode ser dispensada.
Em outro terminal, na raiz deste projeto, baixe o modelo e inicie a conversa:

```bash
ollama pull qwen3:4b-instruct
python3 -m emporio.agent
```

Não há chave de API ou serviço de inferência pago. O download inicial do modelo
exige internet; as conversas usam o servidor local. Os pesos ficam fora do
repositório e não são enviados ao GitHub.

Use `/sair` para encerrar ou `/limpar` para apagar o histórico da sessão. Para ver
quais ferramentas são chamadas, ou executar uma mensagem sem modo interativo:

```bash
python3 -m emporio.agent --trace
python3 -m emporio.agent --trace --message "Quais violões disponíveis custam até R$ 1000?"
```

O modelo padrão é `qwen3:4b-instruct`; `--model` ou `OLLAMA_MODEL` permitem alterá-lo.
`--url` ou `OLLAMA_URL` configuram o servidor, cujo padrão é
`http://127.0.0.1:11434`. O cliente aceita apenas endereços locais, ignora proxies,
não segue redirecionamentos e rejeita nomes de modelo com indicação `cloud`.
Outros modelos precisam suportar ferramentas e os parâmetros usados na API.

Para demonstrar consultas de pedidos de um cliente identificado:

```bash
python3 -m emporio.agent --customer-id 3 --trace
```

Nesse exemplo, o pedido 1 pertence ao cliente da sessão, e o pedido 2 não.
**`--customer-id` simula uma identidade fornecida pela aplicação; não autentica
o usuário.** Qualquer pessoa com acesso ao terminal pode escolher esse argumento.
Uma aplicação publicada precisaria substituir essa simulação por autenticação
real. Informar um nome, e-mail ou ID no chat não troca o cliente da sessão.
Sem esse argumento, a consulta de pedidos fica indisponível.

### Consultas independentes e testes

As consultas e os testes usam somente a biblioteca padrão do Python, com sintaxe
compatível com Python 3.9 ou superior. Não é necessário instalar pacotes ou configurar
chaves de API para executá-los. A extração do PDF usa uma dependência opcional,
descrita adiante. Na raiz do projeto, execute:

```bash
python3 -m emporio.data
```

O comando valida os seis CSVs e apresenta a quantidade de registros de cada
tabela. Em caso de erro, informa o arquivo e o campo ou a estrutura afetada,
retornando código de saída 1. Não exibe dados pessoais dos clientes.

Para carregar outra pasta com os mesmos nomes de arquivos e campos:

```bash
python3 -m emporio.data --data-dir /caminho/para/data
```

Para consultar o catálogo pelo terminal:

```bash
# Produtos disponíveis da categoria Violões, com preço final até R$ 1.000
python3 -m emporio.catalog search --category violoes --max-price 1000

# Busca por termos no nome do produto
python3 -m emporio.catalog search --query "Takamine GD20"

# Consulta por ID, aplicando as condições de pagamento via PIX
python3 -m emporio.catalog show 121 --payment-method pix

# Inclui produtos indisponíveis para verificar sua situação
python3 -m emporio.catalog search --query "Giannini" --include-unavailable
```

Os comandos de catálogo também aceitam `--data-dir`. `--max-price` aceita ponto
ou vírgula decimal, sem separador de milhar. A busca usa o preço final para a
condição de pagamento selecionada; o limite de preço é inclusivo. `standard`
(padrão) considera promoções ativas sem presumir pagamento via PIX.

Para recuperar trechos das políticas, com página e seção de origem:

```bash
python3 -m emporio.policies search "Que horas vocês abrem aos sábados?" --limit 1
python3 -m emporio.policies search "Me arrependi da compra, posso devolver?"
python3 -m emporio.policies show 4
```

`search` retorna até três seções completas por padrão; `--limit` aceita de 1 a 10.
`show` consulta o número de uma seção principal. Não é uma resposta gerada pelo
agente: o comando mostra o texto extraído do manual. Sem termos correspondentes,
ele informa que não encontrou uma seção. Ambos aceitam `--index` para indicar
outro índice, cujo PDF fonte deve estar na mesma pasta.

Para executar os testes:

```bash
python3 -m unittest discover -s tests -v
```

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

Os arquivos estão em `data/`. Os conteúdos originais foram preservados; apenas
os nomes foram simplificados para `categories.csv`, `customers.csv`,
`order_items.csv`, `orders.csv`, `products.csv`, `promotions.csv` e
`politicas_da_loja.pdf`. O índice derivado `politicas_da_loja.json` também está
versionado, permitindo consultar as políticas sem instalar um leitor de PDF.
O `.gitattributes` preserva o formato de quebra de linha dos CSVs originais.


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

### Leitura em memória com a biblioteca padrão

Os CSVs são lidos com `csv.DictReader` e convertidos em dataclasses, que deixam
explícitos os campos de cada entidade. As tabelas com chave primária são
indexadas por ID; os itens de pedido permanecem em uma sequência porque vários
itens podem pertencer ao mesmo pedido.

O volume fornecido permite carregar tudo em memória. Pandas acrescentaria uma
dependência sem necessidade de operações analíticas nesta etapa; SQLite seria
útil para persistência e consultas mais complexas, mas exigiria uma importação
e manutenção de um banco que ainda não precisamos. Os arquivos são relidos
a cada chamada a `load_dataset`; não há atualização automática em segundo plano.

### Conversão e validação dos dados

- Valores monetários e descontos usam `Decimal`, evitando aproximações de `float`.
- IDs e quantidades são inteiros; estoque zero é válido, estoque negativo não.
- Datas são convertidas para `date`, e especificações para um objeto JSON de textos.
- Promoções aceitam os indicadores originais `0` e `1`, convertidos em booleanos;
  descontos devem estar entre 0 e 100.
- Rastreamento, previsão de entrega e observações vazios tornam-se `None`.
  Não presumimos que um pedido tenha sido enviado pela presença ou ausência desses campos.
- Cabeçalhos, número de colunas, campos obrigatórios, chaves primárias duplicadas,
  tabelas vazias e referências entre tabelas são verificados.
- O carregamento é interrompido quando há erro. Ignorar linhas inválidas poderia
  ocultar produtos ou pedidos e produzir respostas incorretas.

As validações conferem a estrutura dos dados, sem decidir elegibilidade para
devolução, acumulação de promoções ou outras regras de atendimento. Essas regras
serão implementadas nas consultas. Os status originais são preservados.

O total histórico de um pedido também é preservado: não o recalculamos a partir
dos preços atuais do catálogo, pois eles não demonstram o preço na data da compra.

Os testes usam `unittest`, disponível no próprio Python. Pytest poderia facilitar
fixtures mais complexas, mas não é necessário para os cenários desta etapa.
Eles não exigem Ollama ou download do modelo: a integração HTTP e o fluxo de
ferramentas são exercitados com respostas simuladas. Isso verifica a aplicação,
sem comprovar a qualidade das respostas de um modelo real.

### Consultas e preços independentes do modelo

`Catalog` recebe um conjunto de dados validado e retorna ofertas estruturadas.
A apresentação no terminal fica separada dos métodos `search_products` e
`get_product`, que poderão ser reutilizados pelas ferramentas do agente.
Busca, disponibilidade e cálculo de preços são executados em Python; o modelo
não precisará estimar esses valores a partir de texto livre.

A busca por nome ignora maiúsculas, acentos e pontuação, procurando todos os
termos em qualquer ordem. A categoria usa o nome completo normalizado
(por exemplo, `violoes` corresponde a `Violões`). Os resultados são ordenados
por preço final, nome e ID. Preferimos essa busca explícita a embeddings neste
catálogo pequeno: filtros de preço e estoque precisam ser exatos, e o resultado
é fácil de testar. Ainda não há busca semântica, sinônimos ou correção de digitação.

As regras aplicadas vêm das seções 3, 6.2 e 7.3 de `data/politicas_da_loja.pdf`:

- Um produto só é considerado disponível quando seu status é `active` e o
  estoque é maior que zero. Um descontinuado com estoque positivo continua
  indisponível. A consulta pelo ID permite consultar e explicar essa situação.
- Apenas promoções com `is_active=1` são aplicadas. As tabelas não contêm datas
  de vigência; o indicador fornecido é a referência, sem inferir campanhas pelo mês.
- O desconto de PIX de 5% é aplicado quando esse pagamento é solicitado e não
  existe promoção ativa para o produto. Não há acumulação de descontos.
- Produtos indisponíveis não recebem uma oferta de desconto; seu preço de tabela
  é preservado para consulta, sem prometer disponibilidade ou reserva de preço.
- São apresentados preço de tabela, percentual e motivo do desconto, e preço
  final. O arredondamento monetário usa duas casas e `ROUND_HALF_UP`; o filtro de
  orçamento usa o mesmo valor arredondado apresentado ao cliente.

**Suposições documentadas:** se houver mais de uma promoção ativa para o mesmo
produto, aplicamos somente a de maior desconto; em empate, usamos o menor ID.
O manual proíbe acumulação, mas não define prioridade entre campanhas. O critério
de desempate e o arredondamento são decisões do protótipo. Se o negócio definir
outra prioridade, a regra poderá ser ajustada em um único lugar.

Cada comando do terminal recarrega os arquivos. Uma instância de `Catalog`, por
sua vez, trabalha com a fotografia recebida na construção e não monitora alterações.

### Recuperação de políticas por seção

O script `scripts/build_policy_index.py` extrai o PDF com `pypdf`, usando o modo
layout para distinguir títulos alinhados à esquerda das listas numeradas recuadas.
O índice contém as dez seções principais, com texto, título, páginas, títulos de
subseções e rótulos de tabelas. A capa e os cabeçalhos/rodapés repetidos são
descartados; os espaços são normalizados, sem reescrever as regras.

Escolhemos seções completas em vez de blocos de tamanho fixo para manter condições
e exceções juntas. Uma seção pode atravessar páginas, e nesse caso todas as páginas
de origem são registradas. Essa abordagem depende do layout deste manual; se ele
mudar, a extração deverá ser revista. Documentos maiores podem exigir subseções
menores, com recuperação do contexto ao redor de cada trecho.

`PolicyStore.search` faz ranking lexical BM25 (frequência dos termos, raridade no
documento e tamanho da seção), com peso adicional para títulos e rótulos de tabelas.
Usa normalização de acentos/maiúsculas, remoção de palavras comuns e um vocabulário
pequeno de sinônimos, como `devolver`/`devolução` e `parcelar`/`parcelamento`.
Isso não equivale a compreensão semântica ou a uma classificação de escopo.
A pontuação ordena os resultados; não representa uma probabilidade de acerto.

Preferimos essa recuperação local a embeddings e banco vetorial porque temos
um único manual curto, não precisamos de outra API e conseguimos testar as
referências e os resultados diretamente. Uma alternativa seria fornecer todo
o PDF extraído ao modelo em cada conversa; isso repetiria conteúdo sem relação
com a pergunta. Embeddings podem ser avaliados posteriormente se a busca lexical
não cobrir as formas de perguntar dos usuários.

O PDF permanece como fonte. O índice registra seu SHA-256 e a versão do extrator;
se o PDF mudar, a consulta falha até que o índice seja regenerado. A assinatura
detecta mudanças no arquivo, sem resolver ambiguidades ou verificar a correção
comercial das políticas. A busca retorna referências e texto, sem decidir
sozinha se uma devolução ou garantia deve ser aprovada.

#### Regeneração do índice

Somente para atualizar a extração, crie um ambiente virtual e instale a dependência
fixada em `requirements-ingest.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-ingest.txt
python3 -m scripts.build_policy_index
python3 -m scripts.build_policy_index --check
```

`--check` compara o índice versionado com uma nova extração, sem escrever arquivos.
Após atualizar o manual, revise o texto, as tabelas e as referências antes de
registrar o novo índice no Git. A geração aceita `--source` e `--output`; o índice
e o PDF usado como fonte precisam ficar na mesma pasta para a consulta funcionar.

#### Ambiguidades preservadas no material

- O contato da seção 1.2 difere do WhatsApp informado na seção 7.
- A tabela de pagamento menciona parcela mínima de R$ 100,00, enquanto a seção
  3.1 detalha limites diferentes para determinadas quantidades de parcelas.
- A regra de frete local informa valores abaixo e acima de R$ 500,00, mas não
  explicita o caso de um pedido exatamente nesse valor.

Essas informações permanecem no texto extraído. O agente deve
identificar a ambiguidade e solicitar esclarecimento à equipe da loja, sem
inventar uma regra para preencher a lacuna. O prompt do agente já instrui esse
comportamento; ele precisa ser avaliado também em conversas reais.

### Modelo local e chamada de ferramentas

Escolhemos Ollama com `qwen3:4b-instruct` para atender à preferência por inferência local,
sem API paga. A versão quantizada tem aproximadamente 2,5 GB e suporta
[chamada de ferramentas](https://ollama.com/library/qwen3:4b-instruct).
O tamanho foi escolhido como ponto de partida para um Mac Apple Silicon com
16 GB de memória; modelos maiores podem melhorar respostas, mas exigem mais
recursos. A velocidade e a qualidade dependem do equipamento e das perguntas.
Não adotamos um provedor remoto por causa da preferência de execução local.
Preferimos a variante `instruct` à variante de raciocínio: as tarefas são consultas
curtas, e a tag `qwen3:4b` disponível no ambiente apontou para um modelo que só
oferece raciocínio e atingiu o limite de geração em uma busca de catálogo.

`emporio/ollama_client.py` implementa somente a chamada HTTP de chat necessária,
conforme a [API oficial](https://docs.ollama.com/api/chat). A biblioteca padrão
é suficiente para esse endpoint; não adicionamos um SDK para essa integração
pequena. O modelo é executado com temperatura 0, contexto de 8192 tokens e saída
limitada a 1024 tokens. O modo de raciocínio explícito fica desativado para reduzir
o trabalho de inferência nesta interação; a qualidade ainda precisa ser validada.

O fluxo segue a [documentação de ferramentas do Ollama](https://docs.ollama.com/capabilities/tool-calling):

1. O modelo recebe a mensagem, o prompt e os esquemas das ferramentas.
2. Se solicitar uma consulta, a aplicação valida os argumentos e executa uma função permitida.
3. O resultado estruturado volta ao modelo, que pode consultar novamente ou responder.

Preferimos um laço explícito a LangChain ou outro framework porque temos poucas
ferramentas de leitura e um único modelo. O fluxo fica visível e testável; não há
execução de código gerado, SQL livre, comandos do sistema ou ferramentas de escrita.
`Toolbox` recarrega as fontes em cada consulta e restringe os argumentos permitidos.
Preços são devolvidos como textos decimais, e produtos indisponíveis não recebem
um preço final de venda no resultado enviado ao modelo.
Se o modelo repetir um tipo genérico em `query` e na categoria correspondente
(por exemplo, `query="violão"` com `category="Violões"`), a ferramenta remove
somente esse filtro redundante. Termos específicos de marca ou modelo continuam
obrigatórios na busca; uma busca sem resultados não é ampliada silenciosamente.
É uma abordagem híbrida: chamada de funções para dados estruturados e recuperação
de texto do manual para fundamentar respostas de políticas (RAG).

### Prompt, histórico e limites

O prompt em `emporio/prompts/system.txt` define a persona, o escopo, a consulta
obrigatória às fontes para fatos da loja, a citação das políticas e o tratamento
de indisponibilidade e ambiguidades. Também instrui o modelo a tratar documentos
e mensagens como dados, sem aceitar instruções que tentem mudar essas regras.
Essas instruções reduzem riscos, mas não garantem que toda resposta seja correta.
Como proteção adicional, respostas diretas sem qualquer ferramenta no turno são
substituídas por uma orientação sobre o escopo da loja, com exceção de uma lista
curta de saudações e agradecimentos. Isso também pode tornar respostas de
esclarecimento mais genéricas. Não é um classificador semântico completo: a
presença de uma consulta não comprova que todas as afirmações estejam fundamentadas.
Antes dessa substituição, `emporio/routing.py` tenta recuperar uma fonte quando
o texto contém um tema explícito conhecido: políticas, acessórios ou número de
pedido. A leitura omitida é executada pelas mesmas ferramentas validadas e seu
resultado volta ao modelo para uma nova resposta. O rascunho sem fonte não é
exibido. Essa recuperação determinística foi adicionada depois que conversas
reais revelaram perguntas de continuação respondidas genericamente.

Escolhemos essa recuperação limitada em vez de liberar respostas sem consulta
ou depender apenas de reforçar o prompt. Ela cobre um vocabulário explícito,
sem pretender interpretar toda paráfrase. Não altera a identidade da sessão,
as regras de acesso ou o limite de chamadas por turno. O modelo continua podendo
escolher ferramentas normalmente; a recuperação só atua quando ele não pede uma.
Quando a última consulta falha, a aplicação usa uma resposta controlada. Negativas
de acesso a pedidos não podem ser substituídas por afirmações do modelo.
Quando há consulta de políticas, a aplicação acrescenta as referências de seção
e página a partir dos resultados das ferramentas, mesmo se o modelo esquecer
de citá-las. Elas identificam as fontes consultadas, sem comprovar que toda
afirmação gerada esteja correta.

O histórico fica somente em memória, limitado às três últimas trocas completas
e a 4000 caracteres, removendo trocas inteiras quando necessário.
Não guardamos os resultados antigos das ferramentas no histórico entre turnos;
o modelo deve consultar novamente quando precisar de fatos. Isso reduz contexto
e evita criar armazenamento permanente de conversas nesta demonstração. Banco
de dados ou Redis não são necessários para essa experiência de uma sessão local.

Cada mensagem admite até seis rodadas de modelo e oito chamadas de ferramentas,
com timeout de 120 segundos por requisição. Isso limita laços de consulta; não
é um timeout global da conversa. Mensagens têm até 2000 caracteres. Falhas não
são adicionadas como turnos completos ao histórico. `--trace` mostra nomes das
ferramentas, sem imprimir seus argumentos ou dados de clientes.

### Isolamento das consultas de pedidos

A ferramenta `get_order` aceita somente o ID do pedido. O cliente é vinculado
pela aplicação ao construir a sessão e não é um argumento disponível ao modelo.
O código compara a titularidade antes de devolver qualquer informação. Um pedido
de terceiro e um inexistente produzem o mesmo erro; telefone, e-mail e notas
internas não são devolvidos. Não existe ferramenta para listar todos os clientes
ou alterar essa identidade.

A fonte continua sendo o CSV fornecido: não consultamos transportadoras e não
prometemos atualizações em tempo real. O total histórico do pedido é preservado.

### Validação da integração local

Ambiente observado: Python 3.9.6, Ollama 0.40.14, Mac Apple Silicon com 16 GB de
memória, modelo `qwen3:4b-instruct` com identificador local `0edcdef34593`.
Os identificadores podem mudar caso o provedor atualize a tag do modelo.

Foram executados 98 testes automatizados sem inferência real, cobrindo dados,
catálogo, políticas, argumentos de ferramentas, isolamento de pedidos, laço de
consultas, histórico, falhas de HTTP e apresentação das respostas.

Na primeira validação do commit `5522a38`, foram observados estes resultados no modelo local:

| Cenário | Resultado observado |
| --- | --- |
| Produto 121 com PIX | Consulta de produto e preço final de R$ 439,20, sem acumular descontos |
| Horário de sábado | Consulta ao manual, horário das 09:00 às 13:00 e referência à seção 2, página 2 |
| Violões disponíveis até R$ 1.000 | Consulta de categorias e produtos; cinco opções com preços e aviso de lista parcial |
| Pergunta sobre a capital da França | Orientação sobre o escopo da loja, sem apresentar a resposta fora do escopo |
| Pedido 1 na sessão do cliente 3 | Consulta autorizada com status, total histórico e rastreamento |
| Pedido 2 na sessão do cliente 3 | Nenhum dado de terceiro revelado; nessa execução o modelo não chamou a ferramenta e recebeu a resposta genérica de escopo |

Essas verificações não são uma avaliação exaustiva e não garantem o mesmo
comportamento em toda conversa. A recusa precisa de acesso a terceiros também
é coberta pelos testes da ferramenta, independentemente da escolha do modelo.
As capturas posteriores também orientam melhorias no fluxo de recuperação,
especialmente nas perguntas de continuação.


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
- A identificação de cliente no terminal é uma simulação, sem autenticação real.
  O isolamento dos pedidos é aplicado em código, mas a identidade precisa vir de
  um mecanismo de autenticação confiável antes de qualquer uso em produção.
- Modelos locais podem errar argumentos, deixar de consultar ferramentas ou usar
  inadequadamente o texto recuperado. Os testes com respostas simuladas não medem
  esse comportamento; conversas reais são necessárias para avaliar o conjunto.
- A busca de políticas depende das palavras e sinônimos conhecidos. Pode retornar
  trechos parcialmente relacionados ou não encontrar paráfrases; ela não substitui
  a avaliação da pergunta e do contexto pelo agente.
- As políticas podem conter ambiguidades. As interpretações adotadas serão
  documentadas conforme forem identificadas e implementadas.

## Uso de assistência de IA

Este projeto está sendo desenvolvido com auxílio de uma ferramenta para codificação chamada Cursor, pela familiaridade que possuo com a mesma tendo em vista já ter utilizado, inclusive no plano pago, para completar código e sugestão de codificação. Isso me ajudou muito em termos de produtividade.

Este registro será atualizado conforme o desenvolvimento avançar.
