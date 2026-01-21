### Alterações

implementei o workflow.py que basicamente faz o mesmo que a demo, diferenças:
- da load do dataset, q faz download pelo monai diretamente (nao pelo mcp)
- e depois faz a chamada ao mcp server para listar os modelos, agora passa a categoria como argumento (q é derivada da label do dataset) depois seria feita pelo agente a escolha do modelo correto

--

### MCP-MONAI

Adicionei o server2.py, q é uma versão simplificada do mcp-monai/server.py, removi os endpoints REST e deixei só a parte do MCP server. Está agora por stdio, implementado como estava na docummentação da criacao de MCP servers(proprio site de MCP). Tentei meter em http, mas estava a ter problemas, se quiseres podes tentar.
Fiz em server2.py para nao estragar o server.py original, pq precisava de alterar tambem o client e nao queria mexer nele.

Para testar essa nova versao do mcp-monai, é so correres o tool_registry.py. Este le o mcp-config.json e descobre as tools do mcp-monai. Usei o meu tool_registry.py apenas porque so queria verificar se funcionava sem ter de mexer no teu codigo.

Isto seria a ideia de introduzir N MCP servers, a partir do ficheior mcp-config.json, onde se define os MCP servers a correr




### Dúvidas / notas

- Server2.py Está como stdio, nao está errado, mas não sei se poderá ser uma limitacao para o futuro
- Não fiz mais pq queria primeiro o teu feedback a certa do q fiz, se faz sentido para ti assim, ou se tens outra ideia de como implementar. 
- Acerca dos mcps, acho q seria interessante introduzir o mcp-config.json na pasta orchestrator, que permitiria uma definição centralizada dos MCP servers a usar, e o orchestrator poderia ler esse ficheiro e iniciar os MCP clients correspondentes. Assim, o orchestrator ficaria mais flexível para adicionar novos MCP servers no futuro. O que achas?
- como tinhamos falado de não introduzir ainda agentes, fiquei por aqui

