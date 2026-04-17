package com.elion.mdm.domain

/**
 * MdmState — Enum que define o estado global do Ciclo de Vida do Agente MDM.
 * Serve como S.S.O.T (Single Source of Truth) para roteamento de UI e execução de serviços.
 */
enum class MdmState {
    /** Estado inicial: Dispositivo zerado, aguardando URL e Token de Enrollment. */
    UNCONFIGURED,

    /** Em transição: Realizando handshake e registro no Backend. */
    ENROLLING,

    /** Enrollado: Dispositivo registrado, recebendo políticas e operando no Dashboard normal. */
    ENROLLED,

    /** Kiosk Ativo: Launcher corporativo em execução e restrições de sistema aplicadas. */
    KIOSK_ACTIVE
}
