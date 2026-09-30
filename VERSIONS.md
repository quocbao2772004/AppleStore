# Version 1 and version 2

This repository has two storefronts. They do not share a database, a payment path, or a catalog.

[Version 1](https://github.com/quocbao2772004/AppleStore/tree/ver1) is Apple Store Online, the tree that was on `main` through June 2025. The shop is PHP (`code/`, `php -S localhost:9000`). The assistant is a separate FastAPI app (`code/controllers/full_api.py`, port 4070) over MySQL. That app calls an OpenAI-compatible API at `https://api.x.ai/v1`, matches an MB Bank transfer, and sends email after a successful payment. Admin pages cover products, categories, orders, users, and reviews. Weekly reports from March and April 2025 are in `report/`. The branch README still has the screenshots and the run notes. A hosted copy was published at https://baitap3.toanphatnd.com/.

Version 2 is [Octopus Store](README.md), this branch. One Python process renders the pages and runs the tool loop against PostgreSQL. The catalog is phones, laptops, headphones, tablets, and smartwatches. The model chooses a tool, Python runs it, and the model writes the reply from that result. Checkout saves the order and does not move money. An admin opens `/tracing` for the current session. Customer and admin quality are the offline suites in `eval/` (500 and 84 cases). Those runs do not call the model. A public demo of this version runs on AWS at https://octopus-store.solanai.us/.

| | Version 1 | Version 2 |
| --- | --- | --- |
| Where | Branch [`ver1`](https://github.com/quocbao2772004/AppleStore/tree/ver1), tag `v1` | Branch `main` |
| Name | Apple Store Online | Octopus Store |
| Catalog | Apple products | Phones, laptops, headphones, tablets, smartwatches |
| Shop | PHP | Python, server-rendered HTML |
| Assistant | FastAPI service next to the shop | Tool loop in the same process |
| Database | MySQL | PostgreSQL |
| Model endpoint in code | `https://api.x.ai/v1` | OpenAI-compatible `base_url` in `.env` |
| Payment | MB Bank transfer, then email | Simulated. The order is saved and no money moves |
| Admin | Catalog, orders, users, reviews, and an admin assistant | Read-only reports, a separate admin assistant, and `/tracing` |
| Written evaluation | Weekly PDFs in `report/` | 500 customer cases and 84 admin cases in `eval/` |
| Public demo | https://baitap3.toanphatnd.com/ | https://octopus-store.solanai.us/ |

Version 1’s history is still on `main` under the commits from 2025. The `ver1` branch points at that tree, so its image paths and `Readme.md` stay as they were.
