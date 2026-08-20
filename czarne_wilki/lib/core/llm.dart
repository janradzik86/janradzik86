class WolfLlm {
  WolfLlm._();
  static final instance = WolfLlm._();
  String voice = 'Hetman';
  String generate(String prompt, {required bool unmasked, required bool offline}) {
    final style = unmasked ? 'BEZ MASKI' : 'z maska';
    final net = offline ? 'OFFLINE' : 'SIEC';
    return 'Hetman ($style / $net / $voice):\n$prompt\n\n'
        'Material lokalny. Kontroler jakosci: ZATWIERDZONE.\n'
        'Czarne Wilki Prawdy – Wszyscy Won!';
  }
}
