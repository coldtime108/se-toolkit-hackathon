# SE Toolkit — Theory Quiz: Question Bank

## Git & Workflow

**Q1.** Describe the Git workflow we followed during the labs from start to finish. Explain what happens at each stage.

> Expect: issue, branch, commit, pull request, review, merge.

**Q2.** You and a teammate both edited the same line in `README.md` on separate branches. What will this lead to? Describe step-by-step how you resolve it.

**Q3.** What is a conventional commit message? Give an example of a correct conventional commit for a bug fix to the /items endpoint.

---

## HTTP & REST API

**Q4.** Describe the main parts of an HTTP request and an HTTP response.

> Expect: method, path, query parameters, headers, body, status code, and response body.

**Q5.** A client calls an API and receives HTTP 200, 401, 403, 404, 500, 502. Explain what each status code usually means, and what kind of problem (if any) you would suspect first in each case.

**Q6.** You open Swagger UI for an unfamiliar API. What specific information can you extract from it about a specific endpoint?

> Expect: endpoints, methods, parameters, authentication, request/response bodies and formats; Swagger acts as a live, testable contract that both sides agree on.

**Q7.** What is the relationship between a database schema, a model object, and business logic?

---

## Security & Authentication

**Q8.** Compare API-key authentication and username/password authentication. How does each work, what is each commonly used for, and what are the main tradeoffs?

**Q9.** Explain the difference between *authentication* and *authorization*. 

**Q10.** You SSH into your VM and need to harden it. Name at least four security measures you would apply and explain why each matters.

> Expect: firewall rules, fail2ban, disabling root SSH login, and disabling password authentication.

---

## Docker & Deployment

**Q11.** What is Docker, and how is running an application with Docker different from running it directly with `uv` in a local Python environment?

**Q12.** Explain the difference between a `Dockerfile` and a `docker-compose.yml` file. What problem does each solve, and how do they relate to each other?

**Q13.** How does Docker layer caching work in principle, and why can Dockerfile order make rebuilds slow?

**Q14.** What is Docker build context, and how can a bad build context make images larger or builds slower?

---

## Testing

**Q15.** What is the difference between a *unit test* and an *end-to-end (E2E) test*? Describe what kinds of bugs each is designed to catch. Give one advantage and one disadvantage of each.

**Q16.** Define *boundary-value analysis*. For a function `get_grade(score: int)` that returns "F" for 0–49, "C" for 50–74, "B" for 75–89, and "A" for 90–100, list the specific boundary values you would test.

---

## Data Pipelines

**Q17.** Explain what an *ETL pipeline* is (what each letter stands for and means). In the context of syncing data from an external API to a local PostgreSQL database, give a concrete example of what happens in each stage.

---

## LLM Agents & Tool Use

**Q18.** Describe the agentic loop step by step, from user input to final answer. Include what happens when the LLM requests a tool call.

**Q19.** If an agent read too little code and gave an incorrect answer about the API, what went wrong in its tool-use strategy?

---

## Bot Architecture & Integration

**Q20.** How to separate Telegram transport code from business logic so the bot can be tested without Telegram?

> Expect: separate handlers (business logic) from transport (Telegram); use CLI `--test` mode or call handlers directly in tests.

**Q21.** Compare LLM-based intent routing with traditional command parsing. Give one advantage and one disadvantage of each.

> Expect: user message → tool definitions → LLM decision → tool execution → feeding results back → final response.

---

## System Design

**Q22.** Draw and describe the architecture of the LMS system we built during the labs. Include all components, how they communicate and are deployed.

> Expect: FastAPI backend + PostgreSQL on VM via Docker Compose; Telegram bot service calling backend API; LLM API (OpenRouter/Qwen) for agent and intent routing; ETL sync from external API; deployment via Docker Compose on remote VM; diagram showing containers, network connections, and external services.
