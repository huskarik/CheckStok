export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api/v1/${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Не удалось подключиться к серверу. Повторите попытку позже.");
  }
  let payload = null;
  if (response.status !== 204) {
    try {
      payload = await response.json();
    } catch (error) {
      if (error.name === "AbortError") throw error;
    }
  }
  if (!response.ok) {
    const error = new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : response.status === 422
          ? "Проверьте обязательные поля и введённые значения."
          : "Не удалось выполнить запрос. Повторите попытку позже.",
    );
    error.status = response.status;
    error.code = payload?.code;
    error.context = payload?.context;
    throw error;
  }
  if (response.status !== 204 && payload === null) {
    throw new Error("Сервер вернул неожиданный ответ. Повторите попытку позже.");
  }
  return payload;
}
