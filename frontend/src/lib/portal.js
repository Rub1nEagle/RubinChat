/**
 * Svelte action: переносит DOM-узел в `document.body` (или иной target)
 * на время жизни компонента. Нужен для оверлеев / модалок: если предок
 * имеет `transform`/`filter`/`perspective`, у потомка ломается
 * `position: fixed` — он начинает позиционироваться относительно
 * предка, а не вьюпорта. Перенос в body обходит эту ловушку.
 */
export function portal(node, target = document.body) {
    target.appendChild(node);
    return {
        destroy() {
            if (node.parentNode === target) {
                target.removeChild(node);
            }
        },
    };
}
