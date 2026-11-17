# Fichas online — A Queda de Corvus City (Django)

Aplicação web simples para fichas de personagem. O **mestre** vê e administra todas as fichas e
registra itens encontrados; cada **jogador** vê e edita só a própria ficha e os itens que o mestre
atribuiu a ela. Interface em português, pensada primeiro para celular.

## 1. Instalar e rodar (primeira vez)

Precisa de Python 3.10+ instalado. Dentro da pasta do projeto:

```bash
# 1) ambiente virtual (isola as dependências)
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

# 2) dependências
pip install -r requirements.txt

# 3) configuração local
cp .env.example .env             # Windows: copy .env.example .env
#    abra o .env e troque DJANGO_SECRET_KEY (comando para gerar está no próprio arquivo)

# 4) banco de dados
python manage.py makemigrations fichas   # cria as migrações do app
python manage.py migrate

# 5) usuário mestre (a senha é pedida de forma oculta)
python manage.py criar_mestre NOME_DO_MESTRE

# 6) cadastra as 48 proficiências da ficha (+ origens e trunfos de EXEMPLO)
python manage.py popular_exemplos

# 7) iniciar
python manage.py runserver
```

Abra http://127.0.0.1:8000/ e entre com o mestre. Nas próximas vezes só ative o ambiente
virtual e rode `python manage.py runserver`.

**Testar no celular (mesma rede Wi-Fi):** descubra o IP do computador (ex.: 192.168.0.15),
adicione-o em `DJANGO_ALLOWED_HOSTS` no `.env` e rode `python manage.py runserver 0.0.0.0:8000`.
No celular abra `http://192.168.0.15:8000/`.

## 2. Cadastrar jogadores

Não existe cadastro público: ninguém consegue se tornar mestre pela internet.
1. Entre como mestre e clique em **Configurações** (abre `/admin/`).
2. Em **Usuários → Adicionar usuário**, informe nome de usuário e senha. Todo usuário novo
   nasce como **jogador** automaticamente.
3. Entregue usuário e senha ao jogador. Ele entra em `/entrar/` e cria a própria ficha.
O mestre também pode criar fichas para qualquer jogador (campo “jogador responsável”).

## 2b. Foto do personagem

Na edição da ficha há o campo “foto do personagem” (no celular abre a câmera ou a galeria).
A foto é reduzida para no máximo 900 px, convertida em JPEG e **sem metadados** (GPS/EXIF), e fica
na pasta `media/` (fora do Git). **Não existe endereço público para as fotos**: elas só saem pela
página protegida `/fichas/<n>/foto/`, que confere se quem pede é o mestre ou o dono da ficha.

## 2c. Pegar e deixar itens

Na ficha, cada item encontrado tem os botões **Pegar** e **Deixar**; cada item da mochila tem **Deixar**.
- **Pegar:** o item sai dos itens encontrados e entra na mochila (se a mochila já tiver 15 itens, aparece um erro). Se a quantidade for maior que 1, ela vai no nome, ex.: “Lanterna (×2)”.
- **Deixar** (item encontrado): fica marcado como “Deixado”, mas continua na área privada para ser pego depois.
- **Deixar** (item da mochila): sai da mochila e volta para os itens encontrados, marcado como “Deixado”.
Mestre e dono da ficha podem usar os botões; qualquer outra pessoa recebe 404. Os botões só aceitam POST (com CSRF).

## 2d. Trunfos (máximo 3)

O próprio jogador escreve os trunfos na ficha (nome e descrição), no máximo **3** por personagem, igual à ficha de papel. O servidor recusa o 4º. Os trunfos cadastrados pelo mestre em `/admin/` (“Trunfos sugeridos”) aparecem como sugestão ao digitar o nome.

## 2e. Enviar vários itens e tabela de itens

- **Tabela de itens** (`Itens encontrados → Tabela de itens`): uma “planilha” em que o mestre cadastra itens predefinidos (nome, categoria, descrição) e edita todas as linhas de uma vez.
- **Enviar itens** (`Itens encontrados → Enviar itens`, ou o botão na ficha): marque uma ou mais fichas, digite a quantidade dos itens da tabela que quer enviar e, se precisar, até 3 itens avulsos. Tudo é criado de uma só vez para cada ficha marcada. Os itens continuam privados (só o mestre e o dono da ficha).

## 3. Configurar origens, proficiências e trunfos

Em **Configurações** (`/admin/`) edite *Origens*, *Proficiências* e *Trunfos*. Desmarcar
“disponível para novas fichas” esconde a opção sem apagar das fichas existentes.
As 48 proficiências da ficha vêm de `popular_exemplos` (a ordem pode ser ajustada pelo campo “ordem”). As origens e os trunfos criados por ele têm “[exemplo]” no nome: substitua pelos do livro.

## 4. Como o código está organizado

| Arquivo | O que faz |
|---|---|
| `config/settings.py` | Configurações (lê o `.env`; SQLite ou PostgreSQL) |
| `fichas/models.py` | Tabelas: papéis, catálogos, ficha, proficiências, itens. **Regras de acesso** em `visiveis_para()` e `eh_mestre()` |
| `fichas/forms.py` | Formulários (o do jogador tem menos campos que o do mestre) |
| `fichas/views.py` | As páginas e as verificações de permissão |
| `fichas/admin.py` | Painel `/admin/` do mestre |
| `templates/`, `static/` | HTML, CSS (`static/css/zumbis.css`) e JS |
| `media/` | Fotos enviadas (criada sozinha, fora do Git) |
| `fichas/tests.py` | Testes automáticos de permissão |

**Como a segurança funciona:** (1) `@login_required` e `@mestre_required` nas views; (2) fichas e itens
são sempre buscados por `visiveis_para(usuario)`, então jogador que troca o número na URL recebe
404; (3) o formulário do jogador nem tem os campos do mestre, e o dono da ficha é definido no
servidor; (4) CSRF e senhas com hash do Django; (5) o HTML só recebe dados que o usuário pode ver.

## 5. Verificações manuais de segurança

Crie dois jogadores (ana e bruno), uma ficha para cada, e um item para a ficha da ana. Anote o
número das fichas na URL (`/fichas/1/`, `/fichas/2/`).
1. Entre como **bruno** e abra a URL da ficha da ana → deve dar **404**. Tente `/fichas/1/editar/` → **404**.
2. Como bruno, abra `/itens/`, `/itens/novo/` e `/itens/1/editar/` → deve dar **403** (“sem permissão”).
3. Como bruno, a lista `/fichas/` mostra só a ficha dele, e a ficha dele não mostra o item da ana.
4. Como **ana**, a ficha dela mostra o item na seção “Itens encontrados”, sem botões de editar.
5. Como bruno, tente `/admin/` → o Django pede login de equipe e recusa.
6. Sem login, abra qualquer URL → redireciona para `/entrar/`.
7. Como bruno, abra `/fichas/1/foto/` (foto da ana) → **404**; sem login → redireciona para `/entrar/`.
8. Como ana, “Ver código-fonte” da página: não deve haver nada de outros jogadores.
Para rodar as versões automáticas destas verificações: `python manage.py test`.

## 6. Decisões de projeto (pontos ambíguos)

- **21 pontos:** interpretado como soma total dos 7 atributos (cada um de 1 a 10). Só é
  orientação: a ficha salva com qualquer soma, e mostra um aviso.
- **Máximos:** Sangue Frio = SF × 3 e Anticorpos = RES × 10, calculados automaticamente; o mestre
  pode definir um valor manual. Valores atuais só o mestre altera; começam cheios.
- **Proficiências:** seguem a ficha de papel: cada uma tem só um **bônus**; campo em branco = o personagem não possui. (O campo “nível” foi removido.)
- **Atributo SOC:** a ficha usa “SOC” (Social); no banco o campo continua com o nome antigo `influencia`.
- **Estado:** PV, DEF, MOV e FADIGA são números simples, editados só pelo mestre (como SF e ANT atuais). Recursos (M W E T D F R) e slots podem ser editados pelo jogador.
- **Mochila:** até 15 itens com “slot”; é separada dos itens encontrados.
- **Itens encontrados:** tabela separada, só o mestre cria/edita.
- **Uma ficha por jogador:** o jogador não consegue criar uma segunda (o botão some e o servidor bloqueia). O mestre pode ter várias fichas no próprio usuário (para NPCs), mas não cria uma segunda para um jogador.
- **Tipo de mochila:** comum (10 slots) ou militar (15 slots), escolhido na ficha no quadro “Slots”. O servidor recusa mais itens do que a mochila comporta e o botão “Pegar” respeita o limite. Hoje o jogador escolhe o tipo sozinho; se quiser que só o mestre decida, é só mover o campo para o formulário do mestre.
- **Erro de acesso:** ficha de outra pessoa dá 404 (não revela que existe); área só do mestre dá 403.
- Não tenho o livro do sistema: os conteúdos de exemplo são fictícios.

## 7. Próximos passos recomendados

1. Preencher origens, proficiências e trunfos reais; ajustar regras de validação do livro.
2. Limite de tentativas de login (ex.: `django-axes`) e HTTPS antes de publicar na internet.
3. Migrar para PostgreSQL (preencha `DB_*` no `.env`, instale `psycopg`, rode `migrate`).
4. Histórico de alterações dos valores de Sangue Frio/Anticorpos; botões rápidos “-1/+1” para o mestre.
5. Itens com categorias, peso e transferência entre jogadores (só depois do MVP estável).
