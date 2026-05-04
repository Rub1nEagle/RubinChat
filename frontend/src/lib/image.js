// Клиентский ресайз и пережатие картинки в JPEG.
// Шифрование GOST на сервере — CPU-bound, и каждый лишний мегабайт
// добавляет секунды. Дешевле сжать заранее, потеря качества для
// мессенджера некритична.

const MAX_DIM = 2000;
const QUALITY = 0.85;

/**
 * Сжимает картинку. GIF не трогаем — иначе потеряем анимацию. Остальные
 * форматы (JPEG/PNG/WebP) приводим к JPEG, ресайзим до MAX_DIM по большей
 * стороне.
 *
 * Возвращает либо исходный File, либо новый File того же имени, но меньше.
 * Если что-то пошло не так — возвращает исходный, чтобы не ломать загрузку.
 */
export async function compressImage(file) {
    if (!file || !file.type) return file;
    if (file.type === "image/gif") return file;
    try {
        const bitmap = await createImageBitmap(file);
        let { width, height } = bitmap;
        const longest = Math.max(width, height);
        const scale = longest > MAX_DIM ? MAX_DIM / longest : 1;
        width = Math.max(1, Math.round(width * scale));
        height = Math.max(1, Math.round(height * scale));

        // OffscreenCanvas есть везде в современных браузерах; если нет —
        // падаем на обычный canvas через document.createElement.
        let canvas;
        if (typeof OffscreenCanvas !== "undefined") {
            canvas = new OffscreenCanvas(width, height);
        } else {
            canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
        }
        const ctx = canvas.getContext("2d");
        if (!ctx) return file;
        ctx.drawImage(bitmap, 0, 0, width, height);
        bitmap.close?.();

        const blob = await (canvas.convertToBlob
            ? canvas.convertToBlob({ type: "image/jpeg", quality: QUALITY })
            : new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY)));
        if (!blob) return file;
        if (blob.size >= file.size) return file; // экономии нет — не подменяем

        const newName = (file.name || "image").replace(/\.[^.]+$/, "") + ".jpg";
        return new File([blob], newName, { type: "image/jpeg" });
    } catch (_) {
        return file;
    }
}
