## Doubts and answers

**Doubt:** Should we worry with authentication
*Answer:* Not applied
**Doubt:** Database for the registry?
*Answer:* Ter uma solucao que seja por exemplo o servidor MCP que ja tem essa funcionalidade que permite configurar servicos dinamicamente, sem recompilar o codigo, ficheiro yaml, pasta etc, de modo que seja facil expor novos servicos MCP (sem ser por codigo)
**Doubt:** Async actions so we could call multiple mcp servers at the same time
*Answer:* Not applied
**Doubt:** Develop backend API that calls these?
*Answer:* Not applied
**Doubt:** Instead of hardcoded services we would have services from config/env/discovery
*Answer:* Not applied
**Doubt:** Logs monitoring and auditing instead of console output
*Answer:* Not applied
**Doubt:** Instead of manual testing we would have frontend, llm or schedule jobs calling the tools
*Answer:* Not applied
**Doubt:** We could never develop a frontend to add MCP servers because headers would change, the supported MCP servers have to be in the code?
*Answer:* Not applied
**Doubt:** Focus on tasks and then adapt to use cases or focus on use cases first
*Answer:* Pensar nos casos de uso e se as tarefas sao encaixaveis. Tem que ser reproduzivel


Notes:
1 - Agent skills (Claude) - expor os agentes mcp em pastas, plataforma dinamica de colocar agentes, sem ir ao codigo
2 - Nao tanto codigo mas tools, nao pensar no que programar mas arranjar ferramentas que encaixem estas coisas
3 - Caso de uso: 1 e 2 sao o foco (podem haver barreiras)
4 - Plataforma dinamica, focar paciente, conceito adicional, facilidade de ser multimodel, registar ferramentas on the fly
5 - Qualquer tipo de dados de paciente seriam caso de uso 3, com datasets publicos com outros relatorios (sem ser FHIR)
6 - Sistema que consoante o tipo de dados que entra, orchestrar e automatizar a saída (aquele agente faz isto, por isso vou mandar para ele)
7 - Contribuicoes cientificas e bom caso de uso (o caso da pseudoanonimização era bom)
8 - Ler as referencias
9 - Aproveitar MCP e a onda
10 - Definir milestones, meter tarefas