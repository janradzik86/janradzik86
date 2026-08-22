class WolfMsg {
  WolfMsg(this.role, this.content);
  final String role;
  final String content;
}

class WolfStore {
  WolfStore._();
  static final instance = WolfStore._();
  final messages = <WolfMsg>[
    WolfMsg('system', 'Czarne Wilki Prawdy – Wszyscy Won! Historia SQLite gotowa.'),
  ];
  void add(String role, String content) => messages.add(WolfMsg(role, content));
}
