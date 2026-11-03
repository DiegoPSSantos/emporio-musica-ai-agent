# Empório da Música — agente de atendimento

Protótipo em Python para o desafio técnico de AI Engineer da Artefact.
O objetivo é auxiliar o atendimento de uma loja fictícia de instrumentos
musicais, respondendo com base nos dados da operação e nas políticas fornecidas.

## Estado atual e execução

A leitura e validação dos dados, as consultas ao catálogo e a recuperação de
trechos das políticas estão implementadas. A conversa com o agente e a integração
com o modelo ainda não estão disponíveis.

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

Essas informações permanecem no texto extraído. A integração futura deverá
identificar a ambiguidade e solicitar esclarecimento à equipe da loja, sem
inventar uma regra para preencher a lacuna.


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
- Carregar os dados de clientes não implementa autenticação nem autoriza expô-los
  na conversa. A restrição de consultas de pedidos ainda será implementada.
- As consultas de catálogo ainda exigem argumentos explícitos, sem interpretação
  de linguagem natural ou recomendação automática de alternativas.
- A busca de políticas depende das palavras e sinônimos conhecidos. Pode retornar
  trechos parcialmente relacionados ou não encontrar paráfrases; ela não substitui
  a avaliação da pergunta e do contexto pelo agente.
- As políticas podem conter ambiguidades. As interpretações adotadas serão
  documentadas conforme forem identificadas e implementadas.

## Uso de assistência de IA

Este projeto está sendo desenvolvido com auxílio de uma ferramenta para codificação chamada Cursor, pela familiaridade que possuo com a mesma tendo em vista já ter utilizado, inclusive no plano pago, para completar código e sugestão de codificação. Isso me ajudou muito em termos de produtividade.

Este registro será atualizado conforme o desenvolvimento avançar.
