# Octopus Store

Octopus Store is a Vietnamese storefront for phones, laptops, headphones, tablets, and smartwatches. Prices come from a scrape of [Thế Giới Di Động](https://www.thegioididong.com/) and the storefront shows them as Hà Nội reference prices.

The customer assistant and the admin assistant are each one LangGraph. Python runs a single read-only tool, then the model writes the reply. Checkout saves the order through `place_shop_order`. The invoice says the money has not been taken. A transfer receipt can show a VietQR. A later đối soát marks the order paid only after a matching credit, then sends a confirmation email. Cash on delivery does not call the bank.

This branch is version 2. Version 1, Apple Store Online, is compared in [`VERSIONS.md`](VERSIONS.md). A public demo of this version runs on AWS at https://octopus-store.solanai.us/. That host does not update itself when this branch changes, and the copy there still has the older checkout.

## System flow

One Python process renders the pages and runs both assistants. PostgreSQL holds the catalog and the orders. Qdrant holds warranty passages. RabbitMQ only carries new documents to the embedding worker. The offline eval does not call the model, either graph, or Qdrant.

```mermaid
flowchart TD
  shopper["Shopper browser"]
  pages["server.py renders HTML"]
  chat["POST /tro-ly"]
  shop["LangGraph in agent/graph.py"]
  intent["intent: understand_turn"]
  guards["Python guards"]
  tool["tool node"]
  explain["explain node"]
  pg[("PostgreSQL")]
  qd[("Qdrant store_documents")]
  reply["Reply and cards"]

  shopper --> pages
  shopper --> chat --> shop --> intent --> guards
  guards -->|"ask, refuse, or no tool"| explain
  guards -->|"catalog, stock, orders, or warranty"| tool
  tool --> pg
  tool --> qd
  tool --> explain
  explain --> reply --> shopper
```

`understand_turn` asks the provider for one JSON object: the current requirements and the next action. Python then applies the shop rules. A vague wish asks for a budget before any search. A named model is searched at once. Free-text “muốn mua” does not open checkout. A warranty question does not borrow another brand’s terms.

If the action is `ask`, `refuse`, or empty, the graph skips the tool and goes to `explain`. Otherwise `tool` runs exactly one of `search_products`, `list_category`, `get_product`, `compare_products`, `check_inventory`, `list_orders`, or `search_documents`. `list_category` is the overview of one category when the shopper names no brand and no budget. Catalog cards stay in the order `search_products` ranked. `explain` writes the sentence. It does not pick a different product list.

```mermaid
flowchart TD
  admin["Admin /admin/assistant"]
  adminGraph["LangGraph in admin_agent/graph.py"]
  intent["intent"]
  guards["Python guards"]
  report["one read-only report"]
  explain["explain"]
  none["no tool"]

  admin --> adminGraph --> intent --> guards
  guards -->|"delete, edit, or place an order"| none --> explain
  guards -->|"summary, sales, inventory, orders, or queue"| report --> explain
```

The admin graph is the same shape: intent, one report or none, then explain. Reports are `store_summary`, `sales_report`, `inventory_report`, `order_report`, and `work_queue`. A write request selects no tool and answers that the assistant only reads store figures. Cancelled orders stay out of revenue. The model sees the last eight messages. “Cuộc mới” clears that admin thread.

```mermaid
flowchart LR
  upload["Admin /admin/documents"]
  row["Save the file and a rag_documents row"]
  queue["RabbitMQ rag.documents"]
  worker["backend/rag/worker.py"]
  embed["text-embedding-3-small"]
  index[("Qdrant")]

  upload --> row --> queue --> worker --> embed --> index
```

Restarting the shop does not drain that queue. A later warranty question embeds the question with the same model and quotes only the passages that come back.

```mermaid
flowchart LR
  card["Card button Đặt giúp tôi"]
  form["Name, email, phone, address, receive slot"]
  fn["place_shop_order"]
  db[("PostgreSQL")]
  invoice["Invoice email"]
  qr["Receipt"]
  check["Đối soát chuyển khoản"]
  confirm["Confirmation email"]

  card --> form --> fn --> db
  fn --> invoice
  fn --> qr --> check --> confirm
```

The card button opens the form. The form is the only writer. `place_shop_order` changes stock and inserts the order in one statement. A trigger rejects stock below zero and then nothing is inserted. Pay on the form is “Thanh toán khi nhận hàng” or “Chuyển khoản, xem mã trên máy”. The invoice still says “Chưa trừ tiền thật.” After the form is submitted, the assistant posts that same order back in the chat as an invoice. A cash order has no payment code on that card. The earliest receive slot is tomorrow, inside 14 days: morning 8–12, afternoon 13–17, evening 18–21.

On a transfer receipt, `BANK_ACCOUNT` and `BANK_ACCOUNT_NAME` build a VietQR whose transfer content is `OCTO` plus the order id. The amount is the order total. “Đối soát chuyển khoản” reads the last day of MB credits and marks the order paid when the description contains that reference and the credited amount matches. The confirmation subject is “Đã nhận chuyển khoản đơn #{id}”. `paid_at` is set even when that mail fails. Cash on delivery skips the bank. With the account values unset, the receipt shows a local mark in place of the VietQR. A live statement match has not been confirmed from this environment.

```mermaid
flowchart LR
  cases["eval/client and eval/admin"]
  route["offline router"]
  score["Scores on disk"]

  cases --> route --> score
```

Customer eval calls `route()`. Admin eval calls `local_calls`. Live chat does not call either router.

## The store

The home hero and the animated robot button. The button opens Trợ lý AI.

![Home. The gold octopus sits on the black hero, and the robot button is labeled Trợ lý AI.](docs/store-home.jpg)

A category page shows a short reason row when no brand is selected and the search box is empty. The assistant opens over that page.

![The phone category. The reason row sits above the catalog, and the assistant is open.](docs/store-assistant.jpg)

Bảo asks “t muốn mua iphone 16”. The assistant shows that model, the list price 24.990.000đ, and 181 in stock. The thread does not ask for a budget and does not open checkout. “Đặt giúp tôi” on the card is what opens the form.

![The assistant shows one iPhone 16 card after “t muốn mua iphone 16”.](docs/assistant-iphone.jpg)

The product page for that card. The line under the buttons is “Giá tham chiếu, chưa gồm phí.”

![The iPhone 16 product page, with the Hà Nội reference price and 181 machines in stock.](docs/store-product.jpg)

Bảo asks “So sánh iPhone 16 và iPhone 16 Plus”. Two or more machines become one table. Rows that differ are marked. Search replies stay cards.

![The assistant compares iPhone 16 and iPhone 16 Plus in one table.](docs/assistant-compare.jpg)

A warranty question quotes only the passages that were retrieved: the brand, the document title, the passage, and the source link. The reply does not borrow another brand’s terms.

![The assistant quotes the retrieved Apple warranty passage and links the source.](docs/assistant-warranty.jpg)

“Đặt giúp tôi” opens the delivery form. The order is not written until this form is submitted. The shot is cash on delivery, with the receive slot set to the next morning.

![The delivery form in the assistant, filled in before the order is sent.](docs/assistant-checkout.jpg)

After the form is submitted, the assistant posts the order back in the thread as an invoice. This one is order #114, cash on delivery, and it still says “Chưa trừ tiền thật.” The card has no bank code.

![The assistant posts order #114 back in the chat as an invoice.](docs/assistant-invoice.jpg)

## What the shopper sees

The shopper asks in the assistant. A named model is searched immediately. A vague wish asks one budget question first. A comparison of two or more machines is a table. A warranty answer is the retrieved passages, each with its title and source link. Other replies are a short sentence and product cards. Each card has a photo, the specs, the price, the stock, and “Đặt giúp tôi”.

The order is written only after the shopper submits the delivery form. The assistant then shows the order as an invoice in the thread. Both pay methods save the order the same way. The transfer content the shopper copies is `OCTO` plus the order id. Prices on the cards are Hà Nội reference prices.

## Tracing

`/admin/tracing` shows turns from the signed-in admin’s own session: at most 12 traces, kept in memory, cleared with that chat. A span is the question, the chosen tool, the tool result, and the explanation. The page does not store a phone number, address, email, or the API key. It refreshes when a new turn is stored, and **Reload** forces a refresh. Guests are sent to login. A customer account sees “Chỉ quản trị xem được trang này.” The old paths `/trace` and `/tracing` redirect to `/admin/tracing`. The model name is `OPENAI_MODEL`.

A customer turn is stored on the token that asked it. Opening the admin page with a different login does not show that customer’s thread.

## Live customer loop

The live customer assistant is one LangGraph in `backend/agent/graph.py`, pinned to `langgraph==0.6.11` so it imports on Python 3.9. The provider infers intent and current requirements as structured data, then the graph runs one tool and explains.

The three nodes are `intent`, `tool`, and `explain`, compiled once at import. `search_products` still applies SQL hard filters and ranks the cards. The model writes the catalog prose and does not pick a different list. A warranty reply shows the retrieved passages, with the brand, the title, and the source URL. The instruction that limits the model to those passages stays off the shopper’s screen. `route()` and the regex slot parser remain for offline evaluation. Customer chat does not call them. With no API key, `answer_with_openai` returns nothing and the shopper sees an error. The shop does not guess that turn from the offline rules.

Saving an order calls the Postgres function `place_shop_order`. The stock change and the order rows are one statement. A trigger on `products.stock` rejects a write below zero, and that rejection inserts nothing.

## What Python still decides

The model interprets the request and proposes an action. Python keeps the catalog numbers and shop rules. A broad consultation asks for a budget before searching. Chat text cannot open checkout.

| Responsibility | Where |
| --- | --- |
| Infer the full current request from the conversation, including new brand exclusions | `backend/agent/understand.py` |
| SQL, in-stock filter, and a ranking of at most four cards | `backend/agent/retrieve.py` |
| Checkout form, only after the customer presses a product card's “Đặt giúp tôi” button | `backend/server.py` |
| Warranty and policy text. The question and the documents use the same embedding model | `backend/rag/` |
| Save the order as one database function, then send the invoice | `place_shop_order`, `backend/invoice.py` |
| VietQR, đối soát, and the payment confirmation | `backend/payment.py` |

A follow-up that asks for the cheapest option, and does not name a new price, drops the previous budget. For study laptops, that list is the cheapest in-stock machines that still have a discrete GPU or at least 32 GB of RAM. A stated “around X million” budget caps the recommendation cards at X million; an explicit “under X million” cap is exclusive. Run `.venv/bin/python backend/mock.py` for catalog regression cases or add `--live` to check the configured provider with the same conversations.

A product card shows the photo, specs, price, and stock, then a short explanation of why that particular machine fits the request or where it falls short. The provider returns one explanation for each catalog product ID, so every displayed card receives its own text. The tool payload includes the product ID, price, stock, chip, RAM, storage, battery, charging, screen, GPU, and camera details. Color is asked only when the customer is closing a purchase.

| Tool | When |
| --- | --- |
| `search_products` | Search and recommend. The shop shows at most four cards. Eval also scores cutoffs of 10 and 20. |
| `list_category` | What the shop carries in one category, with no brand and no budget. |
| `get_product` | The customer names one product or one configuration. |
| `compare_products` | Compare two products. Figures come from the catalog. |
| `check_inventory` | How many units are in stock. |
| `list_orders` | Orders for the signed-in session only. |
| Product card checkout action | Open the checkout form for the selected product. This does not create an order. |
| `search_documents` | Warranty, returns, delivery, and brand terms. This does not return a price or a stock count. |
| refusal | Delete, edit the database, read someone else’s order, or skip the instructions. This is not a model tool. |

An order is written only after the customer submits name, email, phone, address, delivery date, and delivery window. Windows are morning 8–12, afternoon 13–17, and evening 18–21. The earliest day is tomorrow, and the latest is 14 days out. A failed SMTP send keeps the order. The invoice says “Chưa trừ tiền thật.” A transfer is marked paid only after đối soát finds a matching credit.

## Warranty documents

A question about price or stock still uses `search_products`. A question about warranty or policy uses `search_documents`. Python embeds that question with `text-embedding-3-small` and reads the nearest passages from the Qdrant collection `store_documents`. The reply quotes only those passages. If none are close enough, it says that brand’s terms are not in the index. A return, privacy, or software-license file can sit in the same collection, and a warranty question does not retrieve it.

`/admin/documents` is admin-only. The form accepts txt, md, and html up to 2 MB. The page saves the original file, inserts a `rag_documents` row, and publishes `{"id": ...}` to the RabbitMQ queue `rag.documents`. The worker `backend/rag/worker.py` is a separate process: it chunks the file, embeds the chunks with the same model, and upserts Qdrant. Restarting the shop does not drain that queue.

The seed command queues the warranty extracts that were actually readable: Samsung, Apple (iPhone and iPad, Mac, Watch, accessories), Xiaomi, OPPO, vivo, HONOR, realme, Acer Vietnam, Logitech hardware, and Dell accessories. Dell accessories are labeled as not a laptop warranty. Wrong articles, cookie shells, and blocked downloads are not seeded.

```bash
.venv/bin/python backend/rag/worker.py
.venv/bin/python backend/rag/seed.py
```

Qdrant listens on `127.0.0.1:6333` and RabbitMQ on `127.0.0.1:5672`. Where Docker is available, `docker compose -f deploy/local/docker-compose.yml up -d` starts both. The offline eval does not call Qdrant, and its scores are unchanged by that index.

## Admin assistant

`backend/admin_agent/` is a separate package. Live chat is the compiled graph in `graph.py`. `route.py` is the offline router `local_calls`, and it is also the fallback when no API key is set. That fallback answers from the reports and adds “Đang trả lời từ số liệu trong máy.” `reports.py` is the only source of the numbers: summary, sales, inventory, orders, and the review queue. There is no write tool. Cancelled orders are excluded from revenue.

Sales take a period of `today`, `7d`, `30d`, or `all`, and a category of phone, laptop, tablet, headphones, or smartwatch. A follow-up such as “thế còn laptop” keeps the period already in the thread. “Đơn đó” reads the newest order id already shown. A follow-up about stock uses the product name already shown.

The two assistants are not one score. The customer eval measures product help. The admin eval measures the offline router, not the live graph. On that router, prompts that ask to delete or edit data fall through to a read, so the safety task score stays 0. The live graph refuses those prompts and calls no report. That difference is left in the score so a later offline run can be compared. None of those prompts write to the database.

## Offline evaluation

```bash
.venv/bin/python eval/client/evaluate.py
.venv/bin/python eval/admin/evaluate.py
```

Each command writes a report in its own directory. Neither calls the API, calls `place_order`, nor changes stock. `eval/client/baseline/` is the run from before the slot reader was fixed. A new run does not overwrite it. The middle column has no separate file. Those numbers live in [`eval/client/README.md`](eval/client/README.md).

The three columns below are earlier published comparisons of the same 500 customer cases. They are not the file on disk now.

| Metric | Baseline | After the slot fix | After the router |
| --- | ---: | ---: | ---: |
| Intent | 58.0 | 55.0 | 100.0 |
| Argument | 92.9 | 96.5 | 100.0 |
| Exact argument match | 80.5 | 85.3 | 100.0 |
| Tool selection | 49.6 | 49.6 | 100.0 |
| Precision@4 | 63.5 | 77.8 | 96.0 |
| Recall@4 | 10.4 | 19.5 | 27.0 |
| MRR | 0.635 | 0.778 | 0.96 |
| Hit@4 | 63.5 | 77.8 | 96.0 |
| Requirement satisfaction | 91.2 | 91.2 | 91.2 |
| Task success | 50.2 | 59.8 | 87.2 |
| Unauthorized | 0.0 | 0.0 | 0.0 |

That router column also recorded Recall@10 42.0, Recall@20 58.7, Hit@10 96.0, and Hit@20 96.0.

How to read the earlier table:

- The baseline missed because slots were wrong and comparison, inventory, checkout, and refusal had no tool yet. Tool selection at 49.6 is that older tool set.
- Intent drops in the middle column because `256GB` is no longer read as RAM, and `Pro` on an iPhone is no longer read as a MacBook line.
- Hit@4 equals Hit@20 on that run. No case misses the top 4 and then hits inside the top 20.
- Requirement satisfaction, 91.2, was scored only on study recommendations. Card order near the budget was preserved.
- 87.2 is that offline router. The prose on the live chat was not part of that number.

The current customer report is [`eval/client/report.md`](eval/client/report.md). Same 500 cases, still offline, still no model call. Mean search time is 8.4 ms.

| Metric | Current report |
| --- | ---: |
| Intent | 99.8 |
| Argument | 99.9 |
| Exact argument match | 99.7 |
| Tool selection | 100.0 |
| Precision@4 | 97.6 |
| Recall@4 | 26.5 |
| MRR | 0.976 |
| Hit@4 | 97.6 |
| Recall@10 | 40.0 |
| Recall@20 | 50.7 |
| Hit@10 | 97.6 |
| Hit@20 | 97.6 |
| Requirement satisfaction | 72.1 |
| Task success | 84.4 |
| Unauthorized | 0.0 |

Twenty queries have no matching machine, and all twenty return an empty list. Three queries have a match that misses the top 4.

Task success by group on that report: product search 84.7, product detail 62.5, comparison 91.7, recommendation 71.4, inventory 100, order tracking 100, checkout 100, safety 100. Recommendation is the drop: 20 of 70 miss, and almost all of those misses are “MacBook … để code/học AI” searches that return no cards. One intent miss is “máy tính bảng để học”, read as product search while the tool stayed `search_products`. The `use` field is 99.5. Inventory, order tracking, checkout, and safety stay at 100.

Admin eval, 84 cases, in [`eval/admin/report.md`](eval/admin/report.md). The router is `local_calls`.

| Metric | Score |
| --- | ---: |
| Intent | 86.9 |
| Argument | 87.4 |
| Exact argument match | 86.7 |
| Tool selection | 81.0 |
| Task success | 81.0 |
| Unauthorized | 0.0 |

Summary, sales, and the review queue are 100. Inventory tool selection is 75. Orders are 86.7. The safety task score is 0 because delete and edit prompts fall through to a read on the offline router. Unauthorized actions stay at 0.

Metric definitions are in [`eval/client/README.md`](eval/client/README.md) and [`eval/README.md`](eval/README.md).

## Layout

| Path | Role |
| --- | --- |
| [`backend/agent/graph.py`](backend/agent/graph.py) | Customer LangGraph: intent, one tool, explain |
| [`backend/agent/prompts/`](backend/agent/prompts/) | Prompt text for understanding and explaining |
| [`backend/agent/model.py`](backend/agent/model.py) | Provider calls used by the customer graph |
| [`backend/agent/tools.py`](backend/agent/tools.py) | Runs the tool the graph chose |
| [`backend/agent/retrieve.py`](backend/agent/retrieve.py) | SQL and ranking |
| [`backend/agent/understand.py`](backend/agent/understand.py) | Provider interpretation and structured result validation |
| [`backend/agent/slots.py`](backend/agent/slots.py) | Legacy offline evaluation parser; not used by live customer chat |
| [`backend/agent/route.py`](backend/agent/route.py) | Offline customer router |
| [`backend/agent/policy.py`](backend/agent/policy.py) | Offline gate. The live chat does not read this file |
| [`backend/admin_agent/graph.py`](backend/admin_agent/graph.py) | Admin LangGraph: intent, one report or none, explain |
| [`backend/admin_agent/route.py`](backend/admin_agent/route.py) | Offline admin router, and the no-key fallback |
| [`backend/admin_agent/reports.py`](backend/admin_agent/reports.py) | Read-only store figures |
| [`backend/server.py`](backend/server.py) | Store pages, login, orders, tracing |
| [`backend/rag/`](backend/rag/) | Document chunking, embeddings, Qdrant, and the RabbitMQ worker |
| [`deploy/local/`](deploy/local/) | Compose file for local Qdrant and RabbitMQ |
| [`backend/invoice.py`](backend/invoice.py) | HTML invoice over SMTP |
| [`backend/payment.py`](backend/payment.py) | VietQR, bank match, and the payment confirmation |
| [`eval/client/`](eval/client/) | 500 customer cases, the current report, and the baseline |
| [`eval/admin/`](eval/admin/) | 84 admin cases |
| [`frontend/`](frontend/) | CSS and JavaScript. Python renders the HTML |
| [`database/schema.sql`](database/schema.sql) | Catalog tables |
| [`api/suggest.py`](api/suggest.py) | Search-box suggestions |
| [`scraper/`](scraper/) | Catalog crawl. It does not serve the shop |
| [`docs/`](docs/) | Store screenshots used above |
| [`VERSIONS.md`](VERSIONS.md) | Version 1 compared with this store |
| [`deploy/aws/`](deploy/aws/) | AWS demo: bootstrap and operator notes |

```bash
.venv/bin/python backend/test_agent.py
.venv/bin/python backend/test_invoice.py
.venv/bin/python backend/test_payment.py
.venv/bin/python backend/test_receipt.py
```

Those commands do not call the model API, the bank, or SMTP, and they do not place an order.

## Deployed on AWS

The demo is https://octopus-store.solanai.us/. It is this same store, not a second codebase. The host does not pick up this payment flow or the admin graph until someone redeploys it.

One EC2 `t4g.small` in `ap-southeast-1` runs Ubuntu 24.04. PostgreSQL 18 is on that machine. The app listens on `127.0.0.1:8765` under systemd. Caddy terminates HTTPS and proxies to that port. Cloudflare proxies the `octopus-store` name. The security group accepts TCP 80 and 443. Administration is AWS Systems Manager. SSH is not open. The EBS volume is encrypted.

Catalog rows, product images, and the demo customer accounts were copied from the local machine. Local orders and sessions were not. Checkout on the site is still the older simulated checkout. The model key lives on the instance, outside this repository.

The instance is on the AWS Free Plan. The site stops when that plan or its credit ends. The model API is a separate provider and is not covered by the AWS credit. Resource ids, the bootstrap script, and the operator commands are in [`deploy/aws/README.md`](deploy/aws/README.md).

## Run

Local PostgreSQL, database `tgdd_products`.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
psql -d tgdd_products -f database/schema.sql
.venv/bin/python backend/server.py
```

Open http://127.0.0.1:8765. Login and registration both return to the home page. A reload keeps the session.

| Role | Email | Password | Name on this demo |
| --- | --- | --- | --- |
| Customer | `khach@form.local` | `form-khach` | Bảo |
| Admin | `admin@form.local` | `form-admin` | Quản trị |

The customer row is inserted only when it is missing. A fresh insert is named Khách. This demo database has already been renamed to Bảo.

`.env` lives at the repository root and is not committed:

```bash
OPENAI_API_KEY=
base_url=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.6-luna
EMBEDDING_MODEL=text-embedding-3-small
QDRANT_URL=http://127.0.0.1:6333
RABBITMQ_URL=amqp://guest:guest@127.0.0.1:5672/
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
BANK_ID=
BANK_ACCOUNT=
BANK_ACCOUNT_NAME=
BANK_USERNAME=
BANK_PASSWORD=
```

`base_url` is any chat-completions endpoint. With `SMTP_USER` and `SMTP_PASSWORD` empty, the order is still saved and the receipt says the invoice was not sent. A Gmail app password may be shown in groups of four; the store strips those spaces before SMTP login. An empty `BANK_ID` is treated as MB. `BANK_ACCOUNT` and `BANK_ACCOUNT_NAME` are what the VietQR needs. `BANK_USERNAME` and `BANK_PASSWORD` are read only when đối soát asks the bank. To restart, stop the process listening on port 8765 first.

`server.py` creates the account, session, order, and chat tables on startup. Those tables are not fully described in `database/schema.sql`.

## Limits

- The catalog is a scraped snapshot, not a live warehouse. A product that is not in the catalog is a missed task.
- Live product search uses provider-interpreted requirements, SQL hard filters, and ranking. Warranty text is a separate Qdrant index. The offline suites do not call the model or that index.
- 84.4 is the current offline customer router, in `eval/client/report.md`. The sentence in the chat is the model’s sentence. `/admin/tracing` shows the turns of the admin who is signed in.
- The admin offline score is `local_calls`. The live admin graph refuses a delete or an edit. The safety task score of 0 keeps that offline gap.
- A transfer receipt shows a VietQR when the account name and number are set. Đối soát matches `OCTO` plus the order id against the last day of credits. Cash on delivery does not call the bank. A live statement match has not been confirmed from this environment.
- The public AWS host still serves the older checkout until it is redeployed.

## Data

The schema is [`database/schema.sql`](database/schema.sql). Prices are integer VND. `price_vnd` prefers the detail-page price once that page has been read. The view `agent_product_catalog` gathers specs, images, variants, and reviews. Agents filter `is_live_catalog = true` when they should only suggest products that are on sale.

| Table | Contents |
| --- | --- |
| `products` | Category, name, brand, URL, price, condition, full-text search column |
| `product_specifications` | Spec key and value |
| `product_variants` | Storage and configuration |
| `product_images` | Files downloaded under `data/images` |
| `product_offers`, `product_reviews`, `price_history` | Promotions, sample reviews, price over time |
| `discovery_urls`, `sitemap_pages`, `crawl_runs`, `crawl_errors` | Crawl queue and checkpoints |

Crawl again, or resume a run that stopped:

```bash
.venv/bin/python scraper/tgdd_scraper.py --mode all
.venv/bin/python scraper/tgdd_scraper.py --mode details --only-listed --max-details 100
.venv/bin/python scraper/tgdd_scraper.py --mode images
```

`--mode` accepts `categories`, `catalog`, `supplement`, `sitemap`, `details`, and `images`. The crawler waits at least five seconds between requests and records finished URLs in PostgreSQL. `--retry-errors` retries failed URLs. Images land in `data/images/<category>/<id>/`.

```sql
SELECT source_product_id, name, brand, price_vnd
FROM products
WHERE category = 'laptop'
  AND is_live_catalog
  AND search_vector @@ plainto_tsquery('simple', 'asus vivobook')
  AND price_vnd BETWEEN 15000000 AND 25000000
ORDER BY price_vnd;
```

Keep the source URL when writing about a product. Use the data only within the terms that allow it.
