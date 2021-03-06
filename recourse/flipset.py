
# todo enumeration strategy
# todo method for enumeration
# todo improve cost function type implementation ('maxpct' / 'logpct' / 'euclidean')
# todo base_mip / rebuild mip when required

# table
# item | change_in_score | change_in_min_pctile | cost
# optional to score



class Flipset(object):

    df_column_names = ['names',
                       'idx',
                       'size',
                       'total_cost',
                       'start_values',
                       'final_values',
                       'final_score',
                       'final_prediction',
                       'feasible',
                       'flipped']

    def __init__(self, x, variable_names, coefficients, intercept = 0.0):

        assert isinstance(x, (list, np.ndarray))

        x = np.array(x, dtype = np.float_).flatten()
        n_variables = len(x)

        assert isinstance(coefficients, (list, np.ndarray))
        intercept = float(intercept)
        assert np.isfinite([intercept])

        assert isinstance(variable_names, list)
        assert len(variable_names) == n_variables
        assert all(map(lambda s: isinstance(s, str), variable_names))

        self._x = x
        self._n_variables = n_variables
        self._variable_names = variable_names
        self._coefs = np.array(coefficients, dtype = np.float_).flatten()
        self._intercept = intercept
        self._items = []

        self._df = pd.DataFrame(columns = Flipset.df_column_names, dtype = object)
        self._sort_args = {'by': ['size', 'total_cost', 'final_score'], 'inplace': True, 'axis': 0}


    @property
    def x(self):
        return self._x


    @property
    def df(self):
        return self._df


    @property
    def sort_args(self):
        return self._sort_args


    def sort(self, **sort_args):

        if len(sort_args) == 0:
            self._df.sort_values(**self._sort_args)
            return

        if 'by' in sort_args:
            sort_names = sort_args['by']
        else:
            sort_names = list(sort_args.keys())
            sort_args = {}

        assert isinstance(sort_names, list)
        assert len(sort_names) > 0
        for s in sort_names:
            assert isinstance(s, str)
            assert s in self._df.columns

        sort_args['by'] = sort_names
        sort_args['inplace'] = True
        sort_args['axis'] = 0

        self._df.sort_values(**sort_args)
        self._sort_args = sort_args


    @property
    def n_variables(self):
        return self._n_variables


    @property
    def variable_names(self):
        return list(self._variable_names)


    @property
    def coefficients(self):
        return self._coefs


    @property
    def intercept(self):
        return self._intercept


    @property
    def items(self):
        return self._items


    @property
    def yhat(self):
        return self._intercept + np.dot(self._coefs, self._x)

    #### built ins ####


    def __len__(self):
        return len(self._items)


    def __repr__(self):
        return str(self._items)


    #### methods ####

    def predict(self, actions = None):
        return np.sign(self.score(actions))


    def score(self, actions = None):
        if actions is not None:
            return self._intercept + np.dot(self._coefs, self._x + actions)
        else:
            return self._intercept + np.dot(self._coefs, self._x)


    def add(self, items):
        if isinstance(items, dict):
            items = [items]
        assert isinstance(items, list)
        items = list(map(lambda i: self.validate_item(i), items))
        self._items.extend(items)
        self._update_df(items)


    def validate_action(self, a):
        a = np.array(a, dtype = np.float_).flatten()
        assert len(a) == self.n_variables, 'action vector must have %d elements' % self.n_variables
        assert np.all(np.isfinite(a)), 'actions must be finite'
        assert np.count_nonzero(a) >= 1, 'at least one action element must be non zero'
        assert np.not_equal(self.yhat, self.predict(a)), 'actions do not flip the prediction from %d' % self.yhat
        return a


    def validate_item(self, item):
        assert isinstance(item, dict)
        required_fields = ['feasible', 'actions', 'total_cost']
        for k in required_fields:
            assert k in item, 'item missing field %s' % k
        item['actions'] = self.validate_action(item['actions'])
        assert item['total_cost'] > 0.0, 'total cost must be positive'
        assert item['feasible'], 'item must be feasible'
        return item


    def item_to_df_row(self, item):
        x = self.x
        a = item['actions']
        h = self.predict(a)
        nnz_idx = np.flatnonzero(a)
        row = {
            'names': [self.variable_names[j] for j in nnz_idx],
            'idx': nnz_idx,
            'size': len(nnz_idx),
            'start_values': x[nnz_idx],
            'final_values': x[nnz_idx] + a[nnz_idx],
            'total_cost': float(item['total_cost']),
            'final_score': self.score(a),
            'final_prediction': h,
            'feasible': item['feasible'],
            'flipped': np.not_equal(h, self.yhat),
            }

        return row


    def _update_df(self, items):
        if len(items) > 0:
            row_data = list(map(lambda item: self.item_to_df_row(item), items))
            self._df = self._df.append(row_data, ignore_index = True)[self._df.columns.tolist()]
            self.sort()


    def view(self):
        return self._df


    def to_latex(self, name_formatter = '\\textit'):

        self.sort()
        tex_columns = ['names', 'start_values', 'final_values']
        tex_df = self._df[tex_columns]

        # split components for each item
        tex_df = tex_df.reset_index().rename(columns = {'index': 'item_id'})
        df_list = []
        for n in tex_columns:
            tmp = tex_df.set_index(['item_id'])[n].apply(pd.Series).stack()
            tmp = tmp.reset_index().rename(columns = {'level_1': 'var_id'})
            tmp_name = tmp.columns[-1]
            tmp = tmp.rename(columns = {tmp_name: n})
            df_list.append(tmp)

        # combine into a flattened list
        flat_df = df_list[0]
        for k in range(1, len(df_list)):
            flat_df = flat_df.merge(df_list[k])

        # drop the merge index
        flat_df = flat_df.drop(columns = ['var_id'])

        # index items by item_id
        flat_df = flat_df.sort_values(by = 'item_id')
        flat_df = flat_df.rename(columns = {'item_id': 'item'})
        flat_df = flat_df.set_index('item')


        # add another column for the latex arrow symbol
        idx = flat_df.columns.tolist().index('final_values')
        flat_df.insert(loc = idx, column = 'to', value = ['longrightarrow'] * len(flat_df))

        # name headers
        flat_df = flat_df.rename(columns = {
            'names': '\textsc{Feature Subset}',
            'start_values': '\textsc{Current Values}',
            'final_values': '\textsc{Required Values}'})

        # get raw tex table
        table = flat_df.to_latex(multirow = True, index = True, escape = False, na_rep = '-', column_format = 'rlccc')

        # manually wrap names with a formatter function
        if name_formatter is not None:
            for v in self.variable_names:
                table = table.replace(v, '%s{%s}' % (name_formatter, v))

        # add the backslash for the arrow
        table = table.replace('longrightarrow', '$\\longrightarrow$')

        # minor embellishments
        table = table.split('\n')
        table[2] = table[2].replace('to', '')
        table[2] = table[2].replace('{}', '')
        table.pop(3)
        table.pop(3)

        return '\n'.join(table)