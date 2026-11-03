# Empório da Música — Customer Support Agent

A Python prototype for Artefact's AI Engineer technical challenge. The agent helps
customers of a fictional Brazilian musical instrument store by querying its
catalog, orders and policies. The interface, documentation and agent responses
are in English. Supplied source files and official product names remain unchanged.

## Requirements and setup

- Python 3.9 or later. Queries and automated tests use only the standard library.
- [Ollama](https://docs.ollama.com/macos), running locally.
- The `qwen3:4b-instruct` model, approximately 2.5 GB to download.

On macOS with Homebrew:

```bash
brew install ollama
```

If the Ollama server is not already running, start it in a terminal and leave it open:

```bash
ollama serve
```

In another terminal, from the project root:

```bash
ollama pull qwen3:4b-instruct
python3 -m emporio.agent
```

No API key or paid inference service is required. Downloading the model needs an
internet connection; conversations use the local server. Model weights are stored
outside the repository and are not uploaded to GitHub.

Use `/exit` to quit and `/reset` to clear the conversation. To show invoked tool
names or run a single message:

```bash
python3 -m emporio.agent --trace
python3 -m emporio.agent --trace --message "Which acoustic guitars are available for up to BRL 1,000?"
```

`--model` or `OLLAMA_MODEL` overrides the model. `--url` or `OLLAMA_URL` overrides
the server address, which defaults to `http://127.0.0.1:11434`. The client accepts
only local HTTP addresses, bypasses proxies, rejects redirects and rejects model
names containing `cloud`. Alternative models must support tools and the API
parameters used by the client.

### Simulated customer session

```bash
python3 -m emporio.agent --customer-id 3 --trace
```

In the supplied data, order 1 belongs to customer 3, while order 2 does not.
**This flag simulates an identity supplied by the application; it does not
authenticate the user.** Anyone with terminal access can choose another value.
A deployed application would need real authentication. Stating a name, email
or customer ID in chat cannot change the session identity. Without the flag,
order lookup is unavailable.

## Independent queries and tests

Validate all six CSV tables:

```bash
python3 -m emporio.data
python3 -m emporio.data --data-dir /path/to/data
```

The command prints record counts without exposing customer details. Invalid data
produces an actionable file/field error and exit code 1.

Query the catalog:

```bash
python3 -m emporio.catalog search --category "Acoustic guitars" --max-price 1000
python3 -m emporio.catalog search --query "Takamine GD20"
python3 -m emporio.catalog show 121 --payment-method pix
python3 -m emporio.catalog search --query "Giannini" --include-unavailable
```

Catalog commands accept `--data-dir`. Maximum price is inclusive and uses the
rounded final price for the selected payment method. Decimal points or commas
are accepted without thousands separators. The default `standard` payment
condition applies active promotions without assuming PIX. Output uses BRL and
English number formatting, for example `BRL 439.20`.

Retrieve English policy sections with references to the original manual:

```bash
python3 -m emporio.policies search "What are your Saturday opening hours?" --limit 1
python3 -m emporio.policies search "Can I return an online purchase?"
python3 -m emporio.policies show 4
```

These commands display reference text, not a generated answer. `search` returns
up to three complete sections by default; `--limit` accepts 1–10. `show` uses a
main section number. Both accept `--index`; the referenced PDF and source index
must be beside that index. A query with no matching terms reports no result.

Run the automated suite without Ollama or a model download:

```bash
python3 -m unittest discover -s tests -v
```

## Real conversation examples

Five automatically recorded conversations cover two customer messages each.
Responses are preserved exactly as returned by the application, including its
safeguards and references. Each file identifies the model, application commit,
tools and observed response time.

| Conversation | Focus |
| --- | --- |
| [Catalog and follow-up](examples/01_catalog.md) | Budget, availability and a follow-up PIX quote |
| [Promotions and PIX](examples/02_promotions_pix.md) | Promotional pricing and non-stacking discounts |
| [Store policies](examples/03_policies.md) | Opening hours and return conditions with references |
| [Orders](examples/04_orders.md) | Authorized order and attempted access to another customer |
| [Scope](examples/05_scope.md) | An unrelated topic and a request for accessories |

With Ollama running, reproduce the same English scenarios in a separate directory:

```bash
python3 -m scripts.record_examples --output-dir /tmp/emporio-examples
```

`--only 02_promotions_pix` runs one scenario. `--overwrite` explicitly replaces
existing captures. The script records execution errors rather than inventing
successful replies; it does not grade answer correctness. Outputs may vary across
runs. Review generated files before committing and do not manually rewrite
responses to make them look successful.

### Review of the English captures

The five current recordings use application commit `fc561b0` and contain ten
customer messages, with no execution errors. Prices, stock, source references
and order ownership were checked against the supplied data and reference manual.

| Scenario | Observed result |
| --- | --- |
| Catalog and follow-up | Five available options, a partial-list notice and a Yamaha C40 PIX quote of BRL 569.91 |
| Promotions | Product 121 at BRL 439.20, with an explanation that the promotional discount does not stack with PIX |
| Policies | Referenced Saturday hours and an English response about online return conditions |
| Orders | Order 1 retrieved for customer 3; order 2 denied without revealing another customer's details |
| Scope | The unrelated question receives a scope response; cable availability is checked against the manual |

These are observed examples, not a claim of perfect performance. The return answer
still adds unsolicited defect/warranty guidance and does not enumerate every
exclusion in section 4.4. Its wording can sound more definitive than a conditional
policy explanation should. The application has no return-approval or refund tool.
The recorded text is unchanged, so these limitations remain visible for review.

## Source material and English localization

`data/` contains the original contents under simplified filenames: `categories.csv`,
`customers.csv`, `order_items.csv`, `orders.csv`, `products.csv`, `promotions.csv`
and `politicas_da_loja.pdf`. `.gitattributes` preserves original CSV line endings.
`politicas_da_loja.json` is the reproducible Portuguese extraction of that PDF.

`policies.en.json` is a separately versioned English reference translation of all
ten sections. It preserves section identifiers, page references, policy conditions
and ambiguities. The supplied Portuguese PDF remains authoritative. The loader
checks both the PDF's SHA-256 and the original extraction's SHA-256, and verifies
that every section and page reference is covered. A changed source blocks queries
until the English reference has been reviewed and updated.

We retain the supplied materials rather than translating them in place so that
the original evidence, product identities and references remain inspectable.
English category and promotion labels are mapped at the application boundary;
original Portuguese category names remain accepted aliases. The model translates
explanatory product descriptions into English while preserving official names,
addresses, identifiers and tracking codes. Parser fixtures and lookup vocabularies
deliberately retain original-language strings where required.

### Rebuilding the source extraction

Only rebuilding the PDF extraction requires the pinned optional dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-ingest.txt
python3 -m scripts.build_policy_index
python3 -m scripts.build_policy_index --check
```

`--check` compares the Portuguese index against a fresh extraction without writing
files. The generator does not automatically translate an updated manual. After a
source change, review the English translation and update its source signatures
and references. Merely changing a signature does not validate translation quality.

## Technical decisions

### Terminal interface and incremental development

A CLI demonstrates the agent and its lookups without requiring a web frontend.
The challenge permits this interface; a website would add presentation and
communication work before improving the core agent. Each implemented stage has
a separate commit with real progress and validation.

### Structured data in memory

`csv.DictReader` and dataclasses provide explicit entity fields without external
dependencies. Tables with primary keys are indexed by ID; order items remain a
sequence because one order can contain multiple products. The small supplied
dataset fits in memory. Pandas is unnecessary for these operational lookups, and
SQLite would introduce an import and database lifecycle before they are needed.
Each tool reloads its source; a `Catalog` instance itself holds a snapshot.

Validation rejects invalid headers, row widths, empty required fields, empty
tables, duplicate primary keys and broken references. Money and discounts use
`Decimal`; dates use `date`; specifications use JSON objects; flags accept `0/1`.
Stock may be zero but not negative. Missing tracking, delivery estimates and notes
become `None`. Invalid rows stop loading instead of silently hiding records.

### Pricing in Python

A product is available only when its status is `active` and stock is positive.
Discontinued products remain unavailable even if a stock count is present. Only
active promotions apply. A requested PIX payment receives 5% off only when no
promotion is active; discounts never stack. Unavailable products have no final
sale price in tool responses. Historical order totals are not recalculated from
today's catalog prices.

Money is rounded to two decimals with `ROUND_HALF_UP`, and budget filters use the
same rounded price displayed to the customer. Results are ordered by final price,
name and ID. If several promotions are active for a product, the prototype chooses
the largest discount and breaks ties by lowest promotion ID. Rounding and campaign
priority are documented assumptions because the manual does not define them.

The model receives computed prices as decimal strings. It does not perform these
calculations. Name search normalizes accents, case and punctuation. English category
aliases map to source categories. A generic type repeated in both query and category
is removed only when redundant; specific brand/model filters are never silently
dropped. We use explicit filters rather than embeddings for exact price and stock
queries in this small catalog.

Product IDs must come from the catalog or an explicit customer request, not a
numbered list position. Name-based follow-ups must search by name again. An unknown
ID returns an explicit lookup error and is not evidence that a product is out of stock.

### Policy retrieval

The original PDF is extracted with `pypdf` in layout mode, distinguishing main
headings from indented numbered lists. Complete sections retain their conditions
and exceptions, including sections spanning pages. This avoids cutting a rule from
its exclusions, as fixed-size chunks might do. Larger manuals may need smaller
subsections with parent-context retrieval.

Search uses BM25 with additional weight for headings and table labels, normalized
terms, stop words and a small bilingual synonym vocabulary. Scores are ranking
values, not confidence probabilities. The English reference keeps retrieval and
standalone output in English without a translation API. We chose local lexical
retrieval over embeddings and a vector database because there is one short manual
and results are easy to inspect. Sending the entire manual on every request would
repeat irrelevant material. Semantic retrieval can be evaluated if actual queries
show that lexical coverage is insufficient.

### Local model and orchestration

Ollama with [Qwen3:4b-instruct](https://ollama.com/library/qwen3:4b-instruct) meets
the preference for local inference without paid API calls. This quantized model
was selected as a starting point for a 16 GB Apple Silicon Mac. Larger models may
improve quality while requiring more resources. The instruct variant is preferable
to the thinking-only variant encountered during development for these short tasks.

`ollama_client.py` uses the standard library for the single required
[chat endpoint](https://docs.ollama.com/api/chat), avoiding an SDK dependency.
Requests use temperature 0, an 8192-token context and at most 1024 output tokens,
with explicit thinking disabled. Marked thinking blocks are not shown to customers.

The application follows Ollama's [tool-calling flow](https://docs.ollama.com/capabilities/tool-calling):
the model requests a named function, the application validates and executes it,
and the result returns to the model. This is a hybrid approach: function calling
for structured data and retrieval-augmented generation for manual policies.
An explicit loop is sufficient for six read-only tools and one model; LangChain
or another orchestration framework would add abstraction before it is needed.
There is no generated-code execution, free-form SQL, shell tool or write tool.

### Grounding, scope and follow-up recovery

`prompts/system.txt` defines an English-speaking virtual persona, scope, source
lookups, unavailable products, policy exceptions and ambiguous conditions. Source
content is treated as data rather than instructions. Prompts alone do not guarantee
correct behavior.

If the model omits a lookup for a recognized policy topic, accessory request or
explicit order number, `routing.py` triggers a validated read and asks the model
again with that source. The unsupported draft is discarded. This limited fallback
was introduced after real follow-up questions produced generic scope replies.
It is not a general semantic classifier and cannot cover every paraphrase.

Other direct replies without a lookup are replaced with a scope explanation,
except for a short greeting/thanks vocabulary. This can make clarification less
natural. The last tool error produces a controlled response, so an order denial
cannot simply be replaced by the model's final wording. Policy section/page
references are appended from tool results even if the model forgets them.
Having a reference does not prove every generated claim is correct.

### History, limits and privacy

Only the last three completed exchanges, capped at 4000 characters, remain in
memory. Whole exchanges are removed when needed. Old tool results are not carried
between turns; facts must be queried again. No conversation database or Redis is
needed for this single-session demonstration. `/reset` clears that history.

Each message allows at most six model rounds and eight tool calls, with a
120-second timeout per request and a 2000-character input limit. This is not a
global conversation timeout. Failed turns are not committed to history. Trace
output shows tool names rather than arguments or customer records.

`get_order` accepts an order ID, never a customer identity. Ownership is checked
in Python against the session customer. Missing and third-party orders return the
same error. Customer contact details and internal notes are excluded. The data
remain a supplied snapshot without live carrier or production-system integration.

## Validation and known limitations

The automated suite includes 103 tests for data validation, pricing, English
category aliases, policy retrieval and translation freshness, tool arguments,
order isolation, follow-up recovery, history and HTTP failures. HTTP/model replies
are simulated in unit tests; real inference is exercised separately in the five
recorded English conversations. These checks are not an exhaustive evaluation.

Ambiguities deliberately preserved from the manual include different contact
numbers in sections 1 and 7, differing installment minimums in the payment table
and section 3.1, and undefined local shipping for exactly BRL 500.00. The assistant
should explain uncertainty and refer the customer to staff rather than invent a rule.

Other limitations include simulated identity, lexical search coverage, finite
fallback vocabulary and model mistakes in tool selection, source interpretation
or answer completeness. The English reference is a maintained translation, not
an automatic update pipeline. There is no real order mutation, refund approval,
complaint registration or WhatsApp integration.

With more time, I would evaluate larger local models on a broader conversation
set, measure factual consistency and latency, improve follow-up/paraphrase
coverage, add real authentication before publishing order access, resolve manual
ambiguities with the store and connect validated operational APIs. Semantic search
would be considered based on observed retrieval failures rather than by default.

## AI coding assistance

This project uses Cursor as a coding assistant, based on previous familiarity
with the tool, including prior use of a paid plan for code completion and coding
suggestions. This helped with productivity. This record will be updated as
development progresses.
