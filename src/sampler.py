"""
.. module:: mcmc
   :synopsis: Sampler base class
.. moduleauthor:: Adam Moss <adam.moss@nottingham.ac.uk>
"""

from __future__ import print_function
from __future__ import division

import os
import json

import numpy as np

from src.trainer import Trainer
from src.utils.logger import save_ess, create_logger, make_run_dir
from src.utils.evaluation import acceptance_rate, effective_sample_size, mean_jump_distance


class Sampler(object):

    def __init__(self,
                 loglike,
                 args,
                 transform=None,
                 name='test'):

        self.loglike = loglike
        self.x_dim = args.x_dim
        
        if transform is None:
            self.transform = lambda x: x
        else:
            self.transform = transform

        if 'run_num' in args:
            run_num = args.run_num
        else:
            run_num = None

        self.use_mpi = False
        try:
            from mpi4py import MPI
            self.comm = MPI.COMM_WORLD
            self.mpi_size = self.comm.Get_size()
            self.mpi_rank = self.comm.Get_rank()
            if self.mpi_size > 1:
                self.use_mpi = True
        except:
            self.mpi_size = 1
            self.mpi_rank = 0

        self.log = not self.use_mpi or (self.use_mpi and self.mpi_rank == 0)

        if self.log:
            if 'log_dir' in args:
                self.logs = make_run_dir(args.log_dir, run_num, append_run_num=False)
            else:
                self.logs = make_run_dir('logs/%s' % name, run_num)
            log_dir = self.logs['run_dir']
            self._save_params(vars(args))
        else:
            log_dir = None
                
        self.logger = create_logger(__name__)

        self.trainer = Trainer(
                args.x_dim,
                args.dim,
                nslow=args.nslow,
                batch_size=args.batch_size,
                flow=args.flow,
                num_blocks=args.num_blocks,
                num_layers=args.num_layers,
                log_dir=log_dir)

        self.initialise(args)

    def initialise(self, args):
        pass

    def _save_params(self, my_dict):
        my_dict = {k: str(v) for k, v in my_dict.items()}
        with open(os.path.join(self.logs['info'], 'params.txt'), 'w') as f:
            json.dump(my_dict, f, indent=4)

    def _chain_stats(self, samples, mean=None, std=None):
        acceptance = acceptance_rate(samples)
        if mean is None:
            mean = np.mean(np.reshape(samples, (-1, samples.shape[2])), axis=0)
        if std is None:
            std = np.std(np.reshape(samples, (-1, samples.shape[2])), axis=0)
        ess = effective_sample_size(samples, mean, std)
        jump_distance = mean_jump_distance(samples)
        self.logger.info(
            'Acceptance: [%5.4f] min ESS [%5.4f] max ESS [%5.4f] jump distance [%5.4f]' %
            (acceptance, np.min(ess), np.max(ess), jump_distance))
        return acceptance, ess, jump_distance

    def _save_samples(self, samples, weights, logl, min_weight=1e-30, outfile='chain'):
        if len(samples.shape) == 2:
            with open(os.path.join(self.logs['chains'], outfile + '.txt'), 'w') as f:
                for i in range(samples.shape[0]):
                    f.write("%.5E " % max(weights[i], min_weight))
                    f.write("%.5E " % -logl[i])
                    f.write(" ".join(["%.5E" % v for v in samples[i, :]]))
                    f.write("\n")
        elif len(samples.shape) == 3:
            for ib in range(samples.shape[0]):
                with open(os.path.join(self.logs['chains'], outfile + '_%s.txt' % (ib+1)), 'w') as f:
                    for i in range(samples.shape[1]):
                        f.write("%.5E " % max(weights[ib, i], min_weight))
                        f.write("%.5E " % -logl[ib, i])
                        f.write(" ".join(["%.5E" % v for v in samples[ib, i, :]]))
                        f.write("\n")