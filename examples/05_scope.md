# Out-of-scope questions and accessories

Automatically recorded real application conversation. The responses below have not been edited.

Scenario objective: Observe scope handling and a request for accessories.

- Started: 2026-11-03T16:17:01-03:00
- Requested model: `qwen3:4b-instruct`
- Python: 3.9.6
- Application commit: `fc561b0`
- Simulated session customer: none

The scenario objective is not a claim that the result passed review. Responses include application safeguards and source references. Tools may be invoked by the model or the application fallback. Timings are observations from this run, not a benchmark.

## Message 1

**Customer:** What is the capital of France?

Tools invoked: none. Observed time: 0.32 s.

**Assistant:**

I provide customer support for Empório da Música. I can help with musical instruments, prices, stock, orders and store policies. Which of these can I help you with?

## Message 2

**Customer:** Do you sell guitar cables?

Tools invoked: `get_policy_section`. Observed time: 4.12 s.

**Assistant:**

We specialize in musical instruments and do not sell accessories such as guitar cables. If you're looking for instruments or need help with something else, feel free to ask!

Sources consulted: manual, section 1, page 2.
