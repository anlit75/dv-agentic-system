# Tools & Adapters API Reference ⚙️

This section documents the foundational execution tools, LLM clients, and HDL simulator adapters in `dv-agentic-system`.

---

## Tool Interface & Models

The base interfaces and validation schemas for tools and system data types.

::: dv_agentic.tools.interface
    options:
      heading_level: 3

::: dv_agentic.tools.models
    options:
      heading_level: 3

---

## LLM Clients

These clients interact with LLM backends (either via cloud APIs or local model pipelines) to complete system agent queries.

### Base LLM Client Interface
::: dv_agentic.tools.llm.interface
    options:
      heading_level: 4

### Web API LLM Client
::: dv_agentic.tools.llm.api
    options:
      heading_level: 4

### Local LLM Client
::: dv_agentic.tools.llm.local
    options:
      heading_level: 4

---

## Simulator Adapters

These classes adapt Cocotb, pyuvm, and various logic simulators (like GHDL, Icarus, Verilator, Xcelium, and IMC) to be controlled programmatically by our agents.

### Cocotb Base Adapter
::: dv_agentic.tools.adapters.cocotb_base
    options:
      heading_level: 4

### pyuvm Adapter
::: dv_agentic.tools.adapters.pyuvm
    options:
      heading_level: 4

### Simulator Specifics

::: dv_agentic.tools.adapters.ghdl_cocotb
    options:
      heading_level: 5

::: dv_agentic.tools.adapters.icarus
    options:
      heading_level: 5

::: dv_agentic.tools.adapters.verilator
    options:
      heading_level: 5

::: dv_agentic.tools.adapters.xcelium
    options:
      heading_level: 5

::: dv_agentic.tools.adapters.imc
    options:
      heading_level: 5
