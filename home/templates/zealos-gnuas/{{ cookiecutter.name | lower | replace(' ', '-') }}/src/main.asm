    ; Include the Zeal 8-bit OS header file, containing all the syscalls macros.
    .include "zos_sys.asm"

    ; The .text section will be linked at address `0x4000`
    .text

    ; We can start the code here, directly, no need to create a routine, but let's keep it clean.
    .global _start
_start:
    ; Start by printing a message on the standard output. As we know at compile time the message, the length
    ; and the dev we want to write on, we can use S_WRITE3 macro.
    S_WRITE3 DEV_STDOUT, _message, _message_end - _message

_end:
    ; We MUST execute EXIT() syscall at the end of any program.
    ; Exit code is stored in H, it is 0 if everything went fine.
    ld h, a
    EXIT()

    .data
    ; Define a label before and after the message, so that we can get the length of the string
    ; thanks to `_message_end - _message`.
_message: .ascii "Hello Zeal OS!"
_message_end:
