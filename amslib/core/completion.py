from amslib.core.manager import BaseManager



class ArgumentCompletion(BaseManager):

    def _general_db_completion(self, table, column, need_distinct=True, filters={}):
        rval = []
        distinct = ''
        if need_distinct:
            distinct = 'distinct'
        sql = "select {0} {1} from {2} ".format(distinct, column, table)
        vals = []
        wheres = []
        if filters:
            for k,v in filters.iteritems():
                wheres.append("{0}=%s".format(k))
                vals.append(v)

        if wheres:
            sql += " where "
            sql += " and ".join(wheres)
        self.db.execute(sql, vals)
        rows = self.db.fetchall()
        if rows:
            for row in rows:
                if row[0]:
                    rval.append(row[0])
        return rval



    def security_group_id(self, **kwargs):
        filters = {}
        prefixes = {}
        # if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
        #         filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
                filters['region'] = kwargs['parsed_args'].region
        return self._general_db_completion('security_groups', 'security_group_id', False, filters)


    def security_group_vpc(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
                filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
                filters['region'] = kwargs['parsed_args'].region
        return self._general_db_completion('security_groups', 'vpc_id', True, filters)


    def security_group_name(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
                filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        return self._general_db_completion('security_groups', 'name', False)


    def region(self, **kwargs):
        return self._general_db_completion('availability_zones', 'region', True)

    def availability_zone(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
                filters['region'] = kwargs['parsed_args'].region
        return self._general_db_completion('availability_zones', 'availability_zone', False, filters)

    def instance_id(self, **kwargs):
        return self._general_db_completion('hosts', 'instance_id', False)

    def ami_id(self, **kwargs):
        return self._general_db_completion('amis', 'ami_id', False)

    def vpc_id(self, **kwargs):
        return self._general_db_completion('vpcs', 'vpc_id', False)

    def subnet_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
                filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        return self._general_db_completion('subnets', 'subnet_id', False, filters)
