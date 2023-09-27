from pandajedi.jedicore import Interaction


# base class for task setup
class TaskSetupperBase(object):
    def __init__(self, taskBufferIF, ddmIF):
        self.ddmIF = ddmIF
        self.taskBufferIF = taskBufferIF
        self.refresh()

    def refresh(self):
        self.siteMapper = self.taskBufferIF.getSiteMapper()


Interaction.installSC(TaskSetupperBase)
