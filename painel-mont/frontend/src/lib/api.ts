import { useEffect, useState } from "react";

/**
 * Cliente da API.
 *
 * Toda resposta vem envelopada com `dados_demonstrativos`. O hook expõe essa
 * flag para que a interface exiba o aviso permanente enquanto a base oficial
 * não estiver disponível.
 */
export interface Envelope<T> {
  dados_demonstrativos: boolean;
  gerado_em: string;
  dados: T;
}

export interface Estado<T> {
  dados: T | null;
  demo: boolean;
  carregando: boolean;
  erro: string | null;
}

export async function buscar<T>(caminho: string): Promise<Envelope<T>> {
  const resp = await fetch(caminho);
  if (!resp.ok) {
    const corpo = await resp.text();
    throw new Error(`${resp.status} — ${corpo.slice(0, 200)}`);
  }
  return resp.json();
}

/** Hook de leitura. Refaz a busca sempre que a query muda (filtros na URL). */
export function useApi<T>(caminho: string): Estado<T> {
  const [estado, setEstado] = useState<Estado<T>>({
    dados: null,
    demo: false,
    carregando: true,
    erro: null,
  });

  useEffect(() => {
    let vivo = true;
    setEstado((e) => ({ ...e, carregando: true, erro: null }));
    buscar<T>(caminho)
      .then((env) => {
        if (!vivo) return;
        setEstado({
          dados: env.dados,
          demo: env.dados_demonstrativos,
          carregando: false,
          erro: null,
        });
      })
      .catch((e: Error) => {
        if (!vivo) return;
        setEstado({ dados: null, demo: false, carregando: false, erro: e.message });
      });
    return () => {
      vivo = false;
    };
  }, [caminho]);

  return estado;
}
