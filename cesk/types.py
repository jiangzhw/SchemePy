# coding: UTF-8
import copy


class SResult(object):
	def __init__(self, env, ret):
		self.env = env
		self.ret = ret

	def __repr__(self):
		return repr({"env": self.env, "return": self.ret})


class SObject(object):
	value = None

	def to_str(self):
		return str(self)

	def realize(self, env):
		return SResult(env, self)

	@property
	def typename(self):
		return 'object'

	def to_boolean(self):
		if not isinstance(self, SBoolean):
			return True
		elif self.value is True:
			return True
		else:
			return False

	def equal(self, other):
		return type(self) == type(other) and self.value == other.value


class SBaseValue(SObject):
	value = None

	def realize(self, env):
		return SResult(env, self)


nil = None


class SNilObject(SBaseValue):
	value = None

	def __repr__(self):
		return 'nil'

	@staticmethod
	def instance():
		global nil
		if nil is None:
			nil = SNilObject()
		return nil

	@property
	def typename(self):
		return 'nil'


class SNumber(SBaseValue):
	def __init__(self, number):
		self.value = number

	def __repr__(self):
		return str(self.value)

	@property
	def typename(self):
		return 'number'


class SBoolean(SBaseValue):
	def __init__(self, value):
		self.value = value

	def __repr__(self):
		if self.value:
			return 'true'
		else:
			return 'false'

	@property
	def typename(self):
		return 'boolean'


class SString(SBaseValue):
	def __init__(self, value):
		self.value = value[1:-1]

	def __repr__(self):
		return self.value

	@staticmethod
	def value_of(value):
		return SString("\"%s\"" % value)

	@property
	def typename(self):
		return "string"


class SIdentifier(SObject):
	def __init__(self, str):
		self.str = str

	def __repr__(self):
		return "'%s" % self.str

	def realize(self, env):
		return SResult(env, env.find(self.str))

	@staticmethod
	def get_value(env, identifier):
		return identifier.realize(env).ret

	def to_str(self):
		return self.str

	@property
	def value(self):
		return self.str

	@property
	def typename(self):
		return 'symbol'


class SList(SObject):
	def __init__(self):
		self.items = []

	def add(self, item):
		self.items.append(item)

	def __len__(self):
		return len(self.items)

	def __getitem__(self, item):
		return self.items[item]

	@property
	def value(self):
		return self.items

	def __repr__(self):
		str = '('
		for i in range(len(self)):
			item = self[i]
			if i > 0:
				str += ' '
			str += repr(item)
		str += ')'
		return str

	def realize(self, env):
		if len(self) == 0:
			raise Exception("empty list can't be realized!")
		first_symbol = self[0]
		if isinstance(first_symbol, SIdentifier):
			first_symbol = SIdentifier.get_value(env, first_symbol)
		if not first_symbol:
			raise Exception("can't find the symbol %s in env" % self[0])
		tmp = first_symbol.realize(env)
		env = tmp.env
		first_symbol = tmp.ret
		if not isinstance(first_symbol, SCallable):
			raise Exception("%s is not callable" % str(first_symbol))
		proc = first_symbol
		params = self[1:]
		result = SCallable.call_procedure(proc, env, params)
		return result

	@property
	def typename(self):
		return 'list'


class SExprList(SObject):
	def __init__(self):
		self.items = []

	def add(self, item):
		self.items.append(item)

	def __len__(self):
		return len(self.items)

	def __getitem__(self, item):
		return self.items[item]

	@property
	def value(self):
		return self.items

	def __repr__(self):
		str = '['
		for i in range(len(self)):
			item = self[i]
			if i > 0:
				str += ' '
			str += repr(item)
		str += ']'
		return str

	def realize(self, env):
		env.expand_continuation(self.items)
		import cesk.core as core_cesk

		result = core_cesk.run_cesk(env)
		return result

	@property
	def typename(self):
		return 'reprlist'


class SCallable(SObject):
	def __init__(self, params, body):
		self.params = params
		self.body = body

	def do_apply(self, env, params):
		return self.apply(env, params)

	def apply(self, env, params):
		pass

	def after_apply(self, result):
		return result

	@property
	def value(self):
		return [self.params, self.body]

	@staticmethod
	def call_procedure(proc, env, params):
		env = env.down()
		# if it's macro, just pass un-realized params to the proc, else if it's func, realize the params first
		result = proc.after_apply(proc.do_apply(env, params))
		env = env.up()
		result.env = env
		return result

	@property
	def typename(self):
		return 'callable'


class SFunc(SCallable):
	is_reader_macro = False

	def do_apply(self, env, params):
		if self.is_reader_macro:
			return self.apply(env, params)
		param_values = []
		for param in params:
			res = param.realize(env)
			if not res.ret:
				raise Exception("can't find the symbol %s in env" % param)
			param_values.append(res.ret)
			env = res.env
		return self.apply(env, param_values)

	def bind_params_to_env(self, env, params):
		if not isinstance(self.params, list):
			l = SList()
			import copy

			l.items = copy.copy(params)
			env.bind(str(self.params), l)
			return
		count = len(self.params)
		if count != len(params):
			print self.params, params
			raise Exception('%d params needed, while %d params given' % (count, len(params)))
		for i in range(count):
			name = self.params[i]
			value = params[i]
			env.bind(str(name), value)

	def apply(self, env, params):
		self.bind_params_to_env(env, params)
		result = self.body.realize(env)
		return result

	def __repr__(self):
		str = "<proc(" + repr(self.params) + ")>:\n"
		str += repr(self.body)
		str += '\n</proc>'
		return str

	@property
	def typename(self):
		return 'fn'


class SMacro(SFunc):
	def do_apply(self, env, params):
		return self.apply(env, params)

	def expand(self, env, params):
		return self.do_apply(env, params)

	def after_apply(self, result):
		env = result.env
		form = result.ret
		# env = env.up()
		# env = env.down()
		env.expand_continuation([form])
		return result

	@property
	def typename(self):
		return 'macro'


class SNativeFunc(SFunc):
	def apply(self, env, params):
		tmp_params = copy.copy(params)
		tmp_params.insert(0, env)
		result = apply(self.body, tmp_params)
		return result

	@property
	def typename(self):
		return 'native_fn'

