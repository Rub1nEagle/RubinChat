# Фронтенд

Фронтенд — это **SPA на Svelte 4**, собираемое **Vite**, со стилями на
**Tailwind CSS** и собственной рубиновой палитрой. После сборки
получается `frontend/dist/` — статика, которую отдаёт FastAPI.

## Стек

| Слой | Решение |
| --- | --- |
| Компоненты | Svelte 4 |
| Сборка / dev-сервер | Vite 5 |
| Стили | Tailwind CSS 3 + кастомные `tg-*` компоненты + CSS-переменные тем |
| Анимации | `svelte/transition` (`fly`, `fade`, `slide`), `svelte/animate` (`flip`) |
| Иконки | Inline-SVG, без внешних шрифтов |
| Маршрутизация | свой минимальный SPA-роутер на `history.pushState` |
| Состояние | `svelte/store` (`writable`/`derived`), localStorage-обёртка |

Список зависимостей — в [`frontend/package.json`](../frontend/package.json),
точные настройки — в [`vite.config.js`](../frontend/vite.config.js) и
[`tailwind.config.js`](../frontend/tailwind.config.js).

## Структура каталога

```
frontend/
├── index.html              входная страница (Vite); viewport-fit=cover
├── src/
│   ├── main.js             точка входа: ранний выбор темы, --app-height
│   ├── App.svelte          корневой компонент-роутер
│   ├── app.css             Tailwind + общие компоненты (.tg-*) + темы
│   ├── routes/
│   │   ├── Login.svelte
│   │   ├── Register.svelte
│   │   └── Chat.svelte
│   ├── components/
│   │   ├── AuthLayout.svelte         обёртка login/register
│   │   ├── Avatar.svelte             аватар (фото или инициалы)
│   │   ├── PasswordInput.svelte      поле пароля с «глазиком» + Enter-forwarding
│   │   ├── ChatHeader.svelte         шапка переписки, статус собеседника
│   │   ├── ContactList.svelte        список переписок + поиск по всей базе
│   │   ├── MessageList.svelte        лента, разделители дат, бесконечная подгрузка
│   │   ├── MessageBubble.svelte      пузырь: текст / картинка / меню
│   │   ├── MessageMenu.svelte        ПКМ + 3-точки, fixed-positioned dropdown
│   │   ├── MessageInfoModal.svelte   «Информация о сообщении» с коллапсом «Безопасность»
│   │   ├── ProfileModal.svelte       профиль с био, аватаром, fingerprint
│   │   ├── AttachmentImage.svelte    расшифрованная картинка через blob-URL
│   │   ├── AttachmentFile.svelte     баббл-кнопка с иконкой документа: имя/размер, по клику скачивает blob
│   │   ├── ImageViewerModal.svelte   полноэкранный просмотрщик картинки (через portal)
│   │   ├── Composer.svelte           ввод + скрепка → меню «Фото / Файлы» + превью; не блокируется во время upload
│   │   ├── SendingAttachments.svelte баннер «отправляется N%» с разворотом для нескольких вложений
│   │   └── ConfirmDialog.svelte      собственная модалка подтверждения
│   └── lib/
│       ├── router.js       SPA-роутер (path store + navigate)
│       ├── stores.js       session / contacts / messages / conversations / wsState
│       ├── api.js          обёртка fetch + REST-методы; XHR с onProgress для upload
│       ├── ws.js           WebSocket-клиент с автореконнектом
│       ├── format.js       время, дата, инициалы, цвет аватарки, plural, groupHex
│       ├── image.js        клиентский ресайз/JPEG-сжатие перед отправкой
│       └── portal.js       Svelte-action: переносит DOM-узел в body (для модалок/меню над transform-предками)
└── public/                 статика, копируется в dist как есть
```

## Маршрутизация

Все маршруты обслуживает один HTML — Vite собирает `dist/index.html`.
FastAPI отдаёт его на любой не-API путь (`/`, `/register`, `/chat`,
любые опечатки), а внутри клиент сам выбирает, что показать:

```js
$: route =
    $path === "/register" ? "register" :
    $path === "/chat"     ? "chat"     :
    "login";
```

Защита маршрутов — реактивная: если на `/chat` нет сессии, `App.svelte`
синхронно перенаправляет на `/`. И наоборот: уже залогиненный
пользователь не задерживается на `/` или `/register`.

После успешного логина / регистрации вместо SPA-перехода используется
**жёсткий redirect через `window.location.replace("/chat")`**: это
гарантирует свежий mount-цикл `Chat.svelte` с сессией, уже подгруженной
из localStorage, и убирает форму из истории браузера.

## Состояние и сессия

`src/lib/stores.js`:

```
session         { token, user_id, username, private_key_hex }   // localStorage
isAuthenticated derived(boolean)
theme           "dark" | "light"                                // localStorage
contacts        UserProfile[]                                   // в памяти
activePeerId    number | null
messages        []                                              // расшифрованные MessageOut
conversations   { peer_id: { last_message, last_preview, unread_count } }
wsState         "online" | "connecting" | "offline"
```

`session` и `theme` — это `persisted("rubinchat.session", null)`:
writable-стор, синхронизированный с `localStorage`. Logout вызывает
`logout()`, который обнуляет все ключи и стирает значение в
хранилище.

## Сетевые слои

* [`lib/api.js`](../frontend/src/lib/api.js) — четыре пространства имён:
  `auth`, `users`, `messages`, `crypto`.
  - REST-обёртка автоматически добавляет `Authorization: Bearer ...`
    из стора и при 401 логаутит / редиректит на `/`.
  - `messages.upload(...)` использует `XMLHttpRequest` с
    `xhr.upload.onprogress`, чтобы UI мог показывать процент загрузки.
  - `messages.fetchAttachmentBlob(id)` и `users.fetchAvatarBlob(id)`
    скачивают зашифрованный/публичный blob через `fetch` и возвращают
    `Blob`; компонент превращает его в `URL.createObjectURL` для `<img>`.
  - `crypto.unsealBatch(items)` расшифровывает партию сообщений за
    один запрос — заметно быстрее серии `unseal` при открытии чата.
  - `crypto.fingerprint(peerId)` — совместный safety-number разговора.
* [`lib/ws.js`](../frontend/src/lib/ws.js) — `connect()`, `disconnect()`,
  `addListener()`, `send()`. Реконнект через 2 секунды после `close`,
  состояние транслируется в `wsState`.

## Темы и палитра

В [`app.css`](../frontend/src/app.css) описаны две темы (`:root` —
светлая, `.dark` — тёмная) через CSS-переменные с компонентами
`r g b` (не hex), чтобы Tailwind мог собирать opacity-варианты
`bg-tg-accent/40` через `rgb(var(--tg-accent) / <alpha-value>)`.

Палитра — **рубиновая**:

| Токен | Светлая | Тёмная | Где используется |
| --- | --- | --- | --- |
| `tg-bg` | почти-белый ff fafb | глубокий рубин 1a 1216 | основной фон |
| `tg-sidebar` | fb f7f8 | 1a 1216 | левая панель |
| `tg-panel` | белый | 25 1c20 | шапки, попапы |
| `tg-incoming` | f3 f0f1 | 22 1a1e | входящий пузырь |
| `tg-surface` / `surface-hi` | c7 1f46 → e8 4f70 | 5e 1429 → 7a 1a36 | свой пузырь (рубин-градиент) |
| `tg-accent` | c7 1f46 | d6 2b4f | кнопки, ссылки, бейджи |
| `tg-muted` | 6e 6269 | 8a 7986 | вторичный текст |
| `tg-success` / `tg-danger` | стандартные | стандартные | статусы |

Дополнительно в `app.css` определены `.tg-bubble`, `.tg-bubble-out` (с
ruby-градиентом), `.tg-bubble-in`, `.tg-input`, `.tg-button`,
`.tg-button-ghost`, `.tg-card`, и узор `.tg-pattern` (две слоёные сетки
точек).

Переключение темы — `toggleTheme()` из `stores.js`, в `App.svelte`
реактивно ставит/снимает класс `dark` на `<html>`. До mount'а
компонента тема применяется в `main.js` (избегаем «вспышки» белого
при тёмной теме).

## Адаптивная высота под мобильные браузеры

[`main.js`](../frontend/src/main.js) обновляет CSS-переменную
`--app-height` из `window.visualViewport.height` (с фолбэком на
`window.innerHeight`) на `resize`, `scroll` визуального вьюпорта и
`orientationchange`. `Chat.svelte` использует
`style="height: var(--app-height)"`.

`visualViewport.height` сжимается **и** при появлении адресной строки
iOS / Chrome, **и** при экранной клавиатуре. Это и нужно: чат
ужимается ровно на высоту клавиатуры, Composer остаётся над ней, и
iOS перестаёт принудительно скроллить документ, чтобы поднять фокус —
именно эта автопрокрутка раньше оставляла снизу пустое поле. До
инициализации JS действует CSS-фолбэк `100vh` / `100dvh` —
на современных браузерах.

## Ввод сообщения

[`Composer.svelte`](../frontend/src/components/Composer.svelte):

* `<textarea>` с авторесайзом до 160 px; Enter — отправка, Shift+Enter
  — перенос.
* Кнопка-скрепка слева открывает выпадающее меню **«Фото / Файлы»**.
  Меню рисуется НАД скрепкой через [`portal`](../frontend/src/lib/portal.js)
  + `position: fixed` — иначе `transform`-предки (Composer внутри
  `bg-tg-panel` + grid Chat) сломали бы fixed-позиционирование. На
  мобиле меню всё равно открывается вверх, чтобы клавиатура его не
  закрывала.
* Под капотом — два разных `<input type="file">`:
  * **Фото** — `accept="image/jpeg,image/png,image/webp,image/gif"`,
    лимит 20 МБ до сжатия; затем [`lib/image.js`](../frontend/src/lib/image.js)
    ужимает Canvas → JPEG 85 % / 2000 px и диспатчит `pickFile` с
    `kind: "image"`.
  * **Файлы** — без `accept`, лимит 5 МБ (ровно как у сервера, чтобы
    не гонять впустую); диспатчит `pickFile` с `kind: "file"`.
* Состояние `attachment` приходит сверху (`Chat.svelte`), Composer
  показывает превью + статус (compressing / uploading N% / sealing).
  У файлов превью — иконка-документ. Текстовое поле **не блокируется**
  во время загрузки — можно набирать подпись.
* `dispatch("send", { text })` запускает отправку: родитель ждёт
  promise загрузки (если есть), берёт `attachment_id`, шифрует текст
  через `crypto.seal` и шлёт WS-`send` (или REST fallback'ом).

## Лента и пагинация

[`MessageList.svelte`](../frontend/src/components/MessageList.svelte):

* группирует сообщения по дням и вставляет header'ы дат;
* при первом fill'е лента моментально (без анимации) сдвигается вниз —
  пользователь видит свежие сообщения;
* при `pinnedToBottom` новые сообщения подскролливают плавно;
* при `scrollTop ≤ 200 px` диспатчит `loadOlder` — родитель грузит
  следующую партию через `before_id`. Перед prepend'ом ленты компонент
  запоминает `scrollHeight`; в `afterUpdate` подкручивает `scrollTop`,
  чтобы вьюпорт визуально не дёргался.
* сверху индикатор «Загружаем более ранние…» / «Это начало переписки».

## Расшифровка

`Chat.svelte → loadConversation(peerId)`:

1. `messages.list({peerId, limit: 200})` → расставляем плейсхолдеры
   `plaintext: null` сразу, чтобы лента отрисовалась.
2. Приоритетный батч из последних 20 расшифровывается одним
   `crypto.unsealBatch` и применяется к store.
3. Остальное — фоном батчами по 30, от свежих к старым.
   `bgDecryptToken` отменяет работу, если пользователь успел
   переключить чат.

При ошибке расшифровки текст подменяется на
`[ошибка расшифровки: …]`, и в баббле появляется красный значок
«⚠ подпись».

## Картинки и файлы

* В [`MessageBubble.svelte`](../frontend/src/components/MessageBubble.svelte)
  выбор рендера зависит от `attachment.mime_type`:
  - `image/*` → [`AttachmentImage.svelte`](../frontend/src/components/AttachmentImage.svelte)
    на mount качает `GET /api/messages/attachment/{id}` (`fetch` с
    Bearer'ом), создаёт `URL.createObjectURL` и подставляет в `<img>`.
    Если бэкенд вернул `X-Signature-Valid: 0` — рисуем «⚠ подпись».
  - всё остальное → [`AttachmentFile.svelte`](../frontend/src/components/AttachmentFile.svelte):
    карточка с иконкой-документом, оригинальным именем и размером. По
    клику качает blob через `messagesApi.fetchAttachmentBlob`, создаёт
    `<a download={original_filename}>` и кликает по нему программно;
    `URL.revokeObjectURL` отложен на 1 с — чтобы Safari успел начать
    загрузку.
  Текст-подпись (если есть) рендерится под вложением.
* Загрузка к собеседнику: Composer диспатчит файл с `kind`,
  `Chat.svelte` стартует фоновую загрузку с
  `XMLHttpRequest.upload.onprogress` (превью локально создаётся только
  для картинок — для файла blob-URL ни к чему). Над Composer'ом
  показывается баннер
  [`SendingAttachments.svelte`](../frontend/src/components/SendingAttachments.svelte)
  с прогресс-баром; если в полёте несколько вложений — баннер
  сворачивается с разворотом списка.

## Аватары

[`Avatar.svelte`](../frontend/src/components/Avatar.svelte) принимает
`userId`, `hasAvatar`, `avatarVersion`. Если есть — качает blob через
`fetch` и кеширует `URL.createObjectURL` в module-level Map по ключу
`(userId:version)`. Один и тот же аватар не загружается N раз для N
компонентов в DOM. Если нет — рисует круг-градиент с инициалами.
Загрузка/удаление — кнопка-камера на аватаре в `ProfileModal`
(только для своего профиля).

## Анимации

| Где | Что | Как |
| --- | --- | --- |
| Карточки login/register | «всплывают» при загрузке | `animate-pop` keyframe |
| Смена маршрута | плавный fade | `{#key}` + `in:fade` в `App.svelte` |
| Появление сообщения | `fly` снизу + `flip` для упорядочивания | `svelte/transition` + `svelte/animate` |
| Date-разделители | мягкое `fly` сверху | `svelte/transition` |
| Кнопка отправки | `active:scale-90` | Tailwind utility |
| Тосты ошибок | `fly` снизу | `in:fly` + `out:fly` |
| Раскрытие «Безопасность» в модалках | `slide` 180 ms | `svelte/transition` |
| Шеврон коллапсов | `rotate(180deg)` через CSS-transform | reactive style |
| Поле фокуса | рубиновая обводка + `shadow-glow` | `focus-within` + Tailwind |

## Сборка

```bash
cd frontend
npm install         # один раз
npm run build       # frontend/dist/  ← раздаётся FastAPI
npm run dev         # dev-сервер с HMR на :5173, проксирует /api и /ws
```

В Docker `npm run build` выполняется на этапе `frontend` многослойного
Dockerfile, итог копируется в backend-контейнер по пути
`/frontend/dist`. Подробности — в [deployment.md](deployment.md).

## Что фронтенд намеренно НЕ делает

* Не реализует ГОСТ-алгоритмы в JS — это была бы вторая независимая
  крипто-кодобаза. Используются эндпоинты `/api/crypto/seal`,
  `/api/crypto/unseal`, `/api/crypto/unseal-batch`. Цена компромисса
  описана в [security.md](security.md).
* Не управляет несколькими аккаунтами одновременно: localStorage один на
  origin.
* Не сохраняет историю локально — каждое открытие чата заново тянет
  список через REST.
* Нет push-уведомлений и звуков. Typing-индикатор и presence
  (онлайн/был N минут назад) — эфемерные, идут через тот же
  WebSocket-канал, см. [websocket.md](websocket.md#сервер--клиент).
