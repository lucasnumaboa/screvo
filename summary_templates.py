"""
Templates de resumo — cada um ajusta as instruções enviadas à IA.

Cada template é (chave, rótulo, instruções). A chave "geral" é o padrão.
"""

TEMPLATES = [
    ("geral", "Resumo geral", ""),
    ("ata", "Ata de reunião",
     "Formate a resposta como uma ATA DE REUNIÃO: participantes (quando "
     "identificáveis), pauta/assuntos, principais discussões, decisões tomadas "
     "e próximos passos."),
    ("tutorial", "Tutorial / passo a passo",
     "Formate como um TUTORIAL: liste os passos numerados na ordem em que foram "
     "executados, incluindo comandos, cliques e caminhos mencionados."),
    ("doc", "Documentação técnica",
     "Formate como DOCUMENTAÇÃO TÉCNICA: contexto/objetivo, componentes e "
     "tecnologias citadas, fluxo/arquitetura e observações importantes."),
    ("tarefas", "Lista de tarefas",
     "Foque em ITENS DE AÇÃO: liste as tarefas de forma objetiva em uma "
     "checklist (- [ ]), indicando responsável e prazo quando mencionados."),
    ("changelog", "Changelog",
     "Formate como CHANGELOG: agrupe as mudanças demonstradas em seções "
     "Adicionado, Alterado, Corrigido e Removido (omita as vazias)."),
]


def labels():
    return [(key, label) for key, label, _ in TEMPLATES]


def instructions_for(key):
    for k, _, instr in TEMPLATES:
        if k == key:
            return instr
    return ""
